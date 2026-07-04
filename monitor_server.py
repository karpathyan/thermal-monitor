#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import csv
import time
import threading
import multiprocessing
import math
import sys
import psutil
import atexit
from datetime import datetime

# Configurations
PORT = 8888
DIR_PATH = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(DIR_PATH, 'thermal_log.csv')
LOG_INTERVAL = 5 # Log to CSV every 5 seconds
REALTIME_INTERVAL = 1 # Update realtime data every 1 second
REALTIME_BUFFER_LIMIT = 120 # Keep 2 minutes of 1s readings

# State variables
realtime_buffer = []
buffer_lock = threading.Lock()
server_start_time = time.time()

# Stress test processes
stress_processes = []
stress_active = False
stress_start_time = None
stress_duration = 60
stress_lock = threading.Lock()

# Initialize log file
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'cpu_temp', 'fan_speed', 'cpu_usage', 'ram_usage'])

def get_cpu_temp():
    """Gets current CPU package temperature."""
    temps = psutil.sensors_temperatures()
    if not temps:
        return 0.0
    
    # Check coretemp
    if 'coretemp' in temps:
        for t in temps['coretemp']:
            if 'package' in t.label.lower() or 'id 0' in t.label.lower():
                return t.current
        # Fallback to first coretemp sensor
        if temps['coretemp']:
            return temps['coretemp'][0].current
            
    # Check dell_smm
    if 'dell_smm' in temps and temps['dell_smm']:
        return temps['dell_smm'][0].current
        
    # Check any other thermal sensor
    for name, entries in temps.items():
        if entries:
            return entries[0].current
            
    return 0.0

def get_core_temps():
    """Gets temperatures for all individual cores."""
    temps = psutil.sensors_temperatures()
    core_temps = []
    if not temps:
        return core_temps
        
    if 'coretemp' in temps:
        for t in temps['coretemp']:
            # Skip package temperature for individual cores
            if 'package' not in t.label.lower() and 'id 0' not in t.label.lower():
                core_temps.append({
                    'label': t.label or 'Core',
                    'temp': t.current
                })
    elif 'dell_smm' in temps:
        for i, t in enumerate(temps['dell_smm']):
            core_temps.append({
                'label': f'Sensor {i}',
                'temp': t.current
            })
    return core_temps

def get_fan_speed():
    """Gets fan speed in RPM."""
    fans = psutil.sensors_fans()
    if not fans:
        return 0
    for name, entries in fans.items():
        if entries:
            return entries[0].current
    return 0

# Process cache to get accurate process CPU percent
process_cache = {}

def get_top_processes(limit=5):
    """Gets top processes by CPU utilization."""
    global process_cache
    current_pids = set()
    procs_data = []
    
    for proc in psutil.process_iter():
        try:
            pid = proc.pid
            current_pids.add(pid)
            
            # Skip the stress processes themselves from flooding the process list
            # or keep them so the user sees them. Let's keep them but flag them.
            if pid not in process_cache:
                # Initialize
                proc.cpu_percent()
                process_cache[pid] = proc
                cpu = 0.0
            else:
                cpu = process_cache[pid].cpu_percent()
            
            # Normalize to 0-100% representing total CPU power (or total per core)
            # psutil.cpu_percent() can exceed 100% on multi-core systems if we don't divide by cpu count,
            # but usually proc.cpu_percent() is per-core. Let's cap at 100% or divide by cpu_count
            # for a unified standard. Let's keep it as is (percent of one core) but divide by cpu_count
            # in the UI or leave it as standard process percentage. Standard is process percentage (0-100% per core).
            name = proc.name()
            procs_data.append({
                'pid': pid,
                'name': name,
                'cpu_percent': round(cpu, 1)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Clean cache
    process_cache = {pid: proc for pid, proc in process_cache.items() if pid in current_pids}
    
    # Sort by cpu_percent desc
    procs_data.sort(key=lambda x: x['cpu_percent'], reverse=True)
    return procs_data[:limit]

# Background Monitoring Daemon
def monitor_loop():
    print("Background monitoring thread started.")
    last_log_time = 0
    
    # Initialize CPU percent call
    psutil.cpu_percent()
    psutil.cpu_percent(percpu=True)
    
    while True:
        try:
            timestamp = datetime.now().isoformat()
            cpu_temp = get_cpu_temp()
            core_temps = get_core_temps()
            fan_speed = get_fan_speed()
            cpu_usage = psutil.cpu_percent()
            cpu_usage_cores = psutil.cpu_percent(percpu=True)
            ram_usage = psutil.virtual_memory().percent
            top_procs = get_top_processes()
            
            sample = {
                'timestamp': timestamp,
                'cpu_temp': cpu_temp,
                'core_temps': core_temps,
                'fan_speed': fan_speed,
                'cpu_usage': cpu_usage,
                'cpu_usage_cores': cpu_usage_cores,
                'ram_usage': ram_usage,
                'top_processes': top_procs,
                'stress_active': stress_active
            }
            
            # Update memory buffer
            with buffer_lock:
                realtime_buffer.append(sample)
                if len(realtime_buffer) > REALTIME_BUFFER_LIMIT:
                    realtime_buffer.pop(0)
            
            # Log to CSV
            now = time.time()
            if now - last_log_time >= LOG_INTERVAL:
                with open(LOG_FILE, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp,
                        round(cpu_temp, 2),
                        fan_speed,
                        round(cpu_usage, 2),
                        round(ram_usage, 2)
                    ])
                last_log_time = now
                
        except Exception as e:
            print(f"Error in monitor loop: {e}", file=sys.stderr)
            
        time.sleep(REALTIME_INTERVAL)

# CPU Stress Worker
def stress_worker(stop_event):
    # Perform tight mathematical loops to max out a core
    x = 12.34
    while not stop_event.is_set():
        x = x * x
        if x > 1e100:
            x = 12.34
        _ = math.sin(x) + math.cos(x)

def start_stress_test(duration=60):
    global stress_processes, stress_active, stress_start_time, stress_duration
    with stress_lock:
        if stress_active:
            return False
            
        stress_active = True
        stress_start_time = time.time()
        stress_duration = duration
        
        num_cores = multiprocessing.cpu_count()
        stress_processes = []
        
        print(f"Starting CPU stress test on {num_cores} cores for {duration} seconds.")
        
        for _ in range(num_cores):
            stop_event = multiprocessing.Event()
            p = multiprocessing.Process(target=stress_worker, args=(stop_event,))
            p.daemon = True
            p.start()
            stress_processes.append((p, stop_event))
            
        # Timer thread to stop stress test
        def timer():
            time.sleep(duration)
            stop_stress_test()
            
        t = threading.Thread(target=timer)
        t.daemon = True
        t.start()
        return True

def stop_stress_test():
    global stress_processes, stress_active, stress_start_time
    with stress_lock:
        if not stress_active:
            return False
            
        print("Stopping CPU stress test.")
        for p, stop_event in stress_processes:
            try:
                stop_event.set()
                p.terminate()
                p.join(timeout=1.0)
            except Exception as e:
                print(f"Error terminating process: {e}", file=sys.stderr)
                
        stress_processes = []
        stress_active = False
        stress_start_time = None
        return True

atexit.register(stop_stress_test)

# HTTP API and Static File Handler
class APIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to suppress standard HTTP logging to terminal
        pass

    def end_headers(self):
        # Add CORS and caching controls
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith('/api/stress/start'):
            # Parse duration if provided
            duration = 60
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                try:
                    body = self.rfile.read(content_length).decode('utf-8')
                    params = json.loads(body)
                    duration = int(params.get('duration', 60))
                except Exception:
                    pass
            
            success = start_stress_test(duration)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': success,
                'message': 'Stress test started' if success else 'Stress test already active'
            }).encode('utf-8'))
            
        elif self.path.startswith('/api/stress/stop'):
            success = stop_stress_test()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': success,
                'message': 'Stress test stopped' if success else 'Stress test not active'
            }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/api/realtime':
            with buffer_lock:
                data = list(realtime_buffer)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            latest = data[-1] if data else {
                'timestamp': datetime.now().isoformat(),
                'cpu_temp': 0.0,
                'core_temps': [],
                'fan_speed': 0,
                'cpu_usage': 0.0,
                'cpu_usage_cores': [],
                'ram_usage': 0.0,
                'top_processes': [],
                'stress_active': stress_active
            }
            # Inject dynamic stress status details
            if stress_active and stress_start_time:
                elapsed = time.time() - stress_start_time
                latest['stress_time_remaining'] = max(0, int(stress_duration - elapsed))
            else:
                latest['stress_time_remaining'] = 0
                
            self.wfile.write(json.dumps(latest).encode('utf-8'))
            
        elif self.path == '/api/history':
            history = self.read_history_logs()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(history).encode('utf-8'))
            
        elif self.path == '/api/analysis':
            analysis = self.compute_analysis()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(analysis).encode('utf-8'))
            
        else:
            # Map request path to files in current folder
            clean_path = self.path.split('?')[0]
            if clean_path == '/':
                clean_path = '/index.html'
                
            filepath = os.path.join(DIR_PATH, clean_path.lstrip('/'))
            if os.path.exists(filepath) and os.path.isfile(filepath):
                # Serve the static file
                content_type = 'text/plain'
                if filepath.endswith('.html'):
                    content_type = 'text/html'
                elif filepath.endswith('.css'):
                    content_type = 'text/css'
                elif filepath.endswith('.js'):
                    content_type = 'application/javascript'
                elif filepath.endswith('.ico'):
                    content_type = 'image/x-icon'
                    
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.end_headers()
                
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"404 Not Found")

    def read_history_logs(self, max_points=600):
        """Reads CSV history and downsamples it for fast plotting."""
        if not os.path.exists(LOG_FILE):
            return []
        
        rows = []
        try:
            with open(LOG_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({
                        'timestamp': row['timestamp'],
                        'cpu_temp': float(row['cpu_temp']) if row['cpu_temp'] else 0.0,
                        'fan_speed': int(row['fan_speed']) if row['fan_speed'] else 0,
                        'cpu_usage': float(row['cpu_usage']) if row['cpu_usage'] else 0.0,
                        'ram_usage': float(row['ram_usage']) if row['ram_usage'] else 0.0
                    })
        except Exception as e:
            print(f"Error reading history: {e}", file=sys.stderr)
            return []
            
        n = len(rows)
        if n <= max_points:
            return rows
            
        step = n // max_points
        if step < 1:
            step = 1
        return rows[::step]

    def compute_analysis(self):
        """Analyzes history logs to compute cooling metrics."""
        if not os.path.exists(LOG_FILE):
            return {'status': 'no_data', 'message': 'No historical logs found.'}
            
        rows = []
        try:
            with open(LOG_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({
                        'cpu_temp': float(row['cpu_temp']) if row['cpu_temp'] else 0.0,
                        'fan_speed': int(row['fan_speed']) if row['fan_speed'] else 0,
                        'cpu_usage': float(row['cpu_usage']) if row['cpu_usage'] else 0.0,
                    })
        except Exception as e:
            return {'status': 'error', 'message': f'Error reading log: {str(e)}'}
            
        if not rows:
            return {'status': 'no_data', 'message': 'Log database is currently empty.'}
            
        # 1. Idle temperature (cpu_usage < 10%)
        idle_temps = [r['cpu_temp'] for r in rows if r['cpu_usage'] < 10.0]
        avg_idle_temp = sum(idle_temps) / len(idle_temps) if idle_temps else None
        
        # 2. Load temperature (cpu_usage > 70%)
        load_temps = [r['cpu_temp'] for r in rows if r['cpu_usage'] > 70.0]
        avg_load_temp = sum(load_temps) / len(load_temps) if load_temps else None
        max_load_temp = max(load_temps) if load_temps else None
        
        # 3. Maximums
        max_temp = max(r['cpu_temp'] for r in rows)
        max_load = max(r['cpu_usage'] for r in rows)
        max_fan = max(r['fan_speed'] for r in rows)
        
        # 4. Assess performance
        has_high_load = len(load_temps) >= 5 # 25+ seconds of high load
        
        status = 'insufficient_load'
        grade = 'N/A'
        assessment = "No high-load events detected. Run the 60s CPU Stress Test below to measure temperature under 100% CPU capacity."
        color = '#94a3b8' # Slate
        
        if has_high_load:
            if max_load_temp < 72.0:
                grade = 'A+'
                assessment = "Excellent cooling! CPU temperature remains exceptionally low under peak load. The cooling fan and thermal paste installation are perfect."
                color = '#10b981' # Emerald
                status = 'excellent'
            elif max_load_temp < 80.0:
                grade = 'A'
                assessment = "Great cooling effectiveness. CPU runs safely below thermal throttle margins. Fan/paste is operating well."
                color = '#34d399' # Mint
                status = 'good'
            elif max_load_temp < 86.0:
                grade = 'B'
                assessment = "Standard heat levels under load. Normal and safe for standard use cases. Fan is performing correctly."
                color = '#3b82f6' # Blue
                status = 'fair'
            elif max_load_temp < 91.0:
                grade = 'C'
                assessment = "Elevated temperatures detected under load. The cooling holds, but check for airflow restrictions or if thermal paste was spread evenly."
                color = '#f59e0b' # Amber
                status = 'warm'
            elif max_load_temp < 96.0:
                grade = 'D'
                assessment = "Very hot under load. Approaching thermal throttling limits. Recheck cooler mounting pressure, thermal paste, or fan curve settings."
                color = '#f97316' # Orange
                status = 'hot'
            else:
                grade = 'F'
                assessment = "Critical overheating! CPU exceeds 96°C under load, prompting thermal throttling. IMMEDIATELY check if the fan is working, plastic peel is removed from the cooler base, or thermal paste is correctly applied."
                color = '#ef4444' # Red
                status = 'critical'
        else:
            # Judge based on idle temp
            if avg_idle_temp:
                if avg_idle_temp > 60.0:
                    grade = 'D'
                    assessment = "Abnormally high idle temperature (>60°C). The cooling block might not be making full contact with the CPU, or the fan is disconnected."
                    color = '#ef4444'
                    status = 'high_idle'
                elif avg_idle_temp > 50.0:
                    grade = 'C'
                    assessment = "Warm idle temperatures (50-60°C). Suitable for light use. Run the CPU stress test to see if temperatures spike aggressively."
                    color = '#f59e0b'
                    status = 'warm_idle'
                else:
                    grade = 'B'
                    assessment = "Normal idle temperatures (below 50°C). CPU is comfortable at rest. Initiate the CPU Stress Test below to test under peak load."
                    color = '#3b82f6'
                    status = 'good_idle'
                    
        return {
            'status': status,
            'grade': grade,
            'assessment': assessment,
            'color': color,
            'avg_idle_temp': round(avg_idle_temp, 1) if avg_idle_temp else None,
            'avg_load_temp': round(avg_load_temp, 1) if avg_load_temp else None,
            'max_temp': round(max_temp, 1),
            'max_load': round(max_load, 1),
            'max_fan': max_fan,
            'total_samples': len(rows),
            'has_high_load': has_high_load
        }

if __name__ == '__main__':
    # Start monitor thread
    monitor_thread = threading.Thread(target=monitor_loop)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Try binding to port 8888, incrementing if busy
    server = None
    bind_port = PORT
    for _ in range(10):
        try:
            server = socketserver.TCPServer(("", bind_port), APIRequestHandler)
            break
        except OSError:
            print(f"Port {bind_port} busy, trying next...")
            bind_port += 1
            
    if not server:
        print("Could not bind to any port. Exiting.")
        sys.exit(1)
        
    print(f"\n========================================================")
    print(f"  AeroTherm Monitor Server started at:")
    print(f"  http://localhost:{bind_port}/")
    print(f"========================================================\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        stop_stress_test()
        server.shutdown()
