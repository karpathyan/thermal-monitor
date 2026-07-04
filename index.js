// AeroTherm Client JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // API endpoint references
    const API_REALTIME = '/api/realtime';
    const API_HISTORY = '/api/history';
    const API_ANALYSIS = '/api/analysis';
    const API_STRESS_START = '/api/stress/start';
    const API_STRESS_STOP = '/api/stress/stop';

    // State Variables
    let peakTemperature = 0;
    let peakFanSpeed = 0;
    let stressActive = false;
    let timelineChart = null;
    let scatterChart = null;

    // DOM Elements
    const systemStatus = document.getElementById('system-status');
    const systemStatusText = systemStatus.querySelector('.status-text');
    
    // Gauges
    const currentTempEl = document.getElementById('current-temp');
    const peakTempEl = document.getElementById('peak-temp');
    const tempStatusEl = document.getElementById('temp-status');
    const tempGaugeFill = document.getElementById('temp-gauge-fill');

    const currentLoadEl = document.getElementById('current-load');
    const ramUsageEl = document.getElementById('ram-usage');
    const coresCountEl = document.getElementById('cores-count');
    const loadGaugeFill = document.getElementById('load-gauge-fill');

    const currentFanEl = document.getElementById('current-fan');
    const peakFanEl = document.getElementById('peak-fan');
    const fanStatusEl = document.getElementById('fan-status');
    const fanGaugeFill = document.getElementById('fan-gauge-fill');
    const animatedFanIcon = document.getElementById('animated-fan-icon');

    // Report
    const thermalGradeEl = document.getElementById('thermal-grade');
    const scoreRingFill = document.getElementById('score-ring-fill');
    const scoreDescEl = document.getElementById('score-desc');
    const assessmentTextEl = document.getElementById('assessment-text');
    const compIdleEl = document.getElementById('comp-idle');
    const compPeakEl = document.getElementById('comp-peak');
    const compLoadEl = document.getElementById('comp-load');
    const analysisTimeEl = document.getElementById('analysis-time');

    // Stress tester
    const btnStressStart = document.getElementById('btn-stress-start');
    const btnStressStop = document.getElementById('btn-stress-stop');
    const stressStatusDisplay = document.getElementById('stress-status-display');
    const stressTimeEl = document.getElementById('stress-time');
    const stressProgressFill = document.getElementById('stress-progress-fill');

    // Process table
    const processListEl = document.getElementById('process-list');

    // Chart Tabs
    const btnShowHistory = document.getElementById('btn-show-history');
    const btnShowScatter = document.getElementById('btn-show-scatter');
    const timelineChartCanvas = document.getElementById('timeline-chart');
    const scatterChartCanvas = document.getElementById('scatter-chart');

    // Helper: Calculate stroke offset for radial gauges (circumference = 251.3)
    const setGaugeOffset = (element, percent) => {
        if (!element) return;
        const cappedPercent = Math.min(100, Math.max(0, percent));
        const offset = 251.3 - (cappedPercent / 100) * 251.3;
        element.style.strokeDashoffset = offset;
    };

    // Helper: Calculate stroke offset for score ring (circumference = 282.7)
    const setScoreOffset = (percent) => {
        if (!scoreRingFill) return;
        const cappedPercent = Math.min(100, Math.max(0, percent));
        const offset = 282.7 - (cappedPercent / 100) * 282.7;
        scoreRingFill.style.strokeDashoffset = offset;
    };

    // Poll Realtime API
    const updateRealtime = async () => {
        try {
            const res = await fetch(API_REALTIME);
            if (!res.ok) throw new Error("Monitor offline");
            const data = await res.json();
            
            // Re-enable live status badge if it was inactive
            systemStatus.classList.remove('inactive');
            systemStatusText.textContent = "LIVE MONITOR ACTIVE";
            
            // 1. Update Temperature
            const temp = data.cpu_temp;
            currentTempEl.textContent = `${temp.toFixed(1)}°C`;
            
            if (temp > peakTemperature) {
                peakTemperature = temp;
                peakTempEl.textContent = `${peakTemperature.toFixed(1)}°C`;
            }
            
            setGaugeOffset(tempGaugeFill, temp); // Scaled 0 to 100C
            
            // Temperature status coloring & labeling
            tempStatusEl.className = 'badge';
            if (temp < 55) {
                tempStatusEl.textContent = 'Cool';
                tempStatusEl.classList.add('success');
                tempGaugeFill.style.stroke = 'var(--accent-success)';
            } else if (temp < 75) {
                tempStatusEl.textContent = 'Warm';
                tempStatusEl.classList.add('warning');
                tempGaugeFill.style.stroke = 'var(--accent-warning)';
            } else {
                tempStatusEl.textContent = 'Hot';
                tempStatusEl.classList.add('danger');
                tempGaugeFill.style.stroke = 'var(--accent-temp)';
            }

            // 2. Update CPU Load
            const load = data.cpu_usage;
            currentLoadEl.textContent = `${load.toFixed(1)}%`;
            setGaugeOffset(loadGaugeFill, load);
            ramUsageEl.textContent = `${data.ram_usage.toFixed(1)}%`;
            coresCountEl.textContent = data.cpu_usage_cores ? data.cpu_usage_cores.length : '--';

            // 3. Update Fan Speed
            const fan = data.fan_speed;
            currentFanEl.textContent = fan > 0 ? `${fan} RPM` : '0 RPM (Idle)';
            
            if (fan > peakFanSpeed) {
                peakFanSpeed = fan;
                peakFanEl.textContent = `${peakFanSpeed} RPM`;
            }
            
            // Cap speed scale at 4000 RPM for gauge display
            const fanPercent = (fan / 4000) * 100;
            setGaugeOffset(fanGaugeFill, fanPercent);
            
            fanStatusEl.className = 'badge';
            if (fan === 0) {
                fanStatusEl.textContent = 'Inactive';
                animatedFanIcon.classList.remove('spinning');
            } else {
                fanStatusEl.textContent = 'Active';
                fanStatusEl.classList.add('success');
                
                // Adjust animated fan spin speed dynamically based on RPM
                // Speed ranges from 2s (low RPM) to 0.15s (high RPM)
                const spinSecs = Math.max(0.15, 2.0 - (fan / 3000) * 1.8);
                animatedFanIcon.style.setProperty('--fan-spin-speed', `${spinSecs}s`);
                animatedFanIcon.classList.add('spinning');
            }

            // 4. Update Stress test status
            stressActive = data.stress_active;
            if (stressActive) {
                btnStressStart.classList.add('hidden');
                btnStressStop.classList.remove('hidden');
                stressStatusDisplay.classList.remove('hidden');
                
                const timeRemaining = data.stress_time_remaining || 0;
                stressTimeEl.textContent = timeRemaining;
                
                const percent = (timeRemaining / 60) * 100;
                stressProgressFill.style.width = `${percent}%`;
            } else {
                btnStressStart.classList.remove('hidden');
                btnStressStop.classList.add('hidden');
                stressStatusDisplay.classList.add('hidden');
            }

            // 5. Update Processes Table
            if (data.top_processes && data.top_processes.length > 0) {
                processListEl.innerHTML = data.top_processes.map(proc => `
                    <tr>
                        <td><strong>${proc.name}</strong></td>
                        <td><code>${proc.pid}</code></td>
                        <td>
                            <div class="proc-bar-container">
                                <div class="proc-bar">
                                    <div class="proc-fill" style="width: ${Math.min(100, proc.cpu_percent)}%;"></div>
                                </div>
                                <span class="proc-val">${proc.cpu_percent.toFixed(1)}%</span>
                            </div>
                        </td>
                    </tr>
                `).join('');
            } else {
                processListEl.innerHTML = `<tr><td colspan="3" class="table-loading">No active processes monitored.</td></tr>`;
            }

        } catch (err) {
            systemStatus.classList.add('inactive');
            systemStatusText.textContent = "SERVER CONNECTION LOST";
            console.error("Error fetching realtime data: ", err);
        }
    };

    // Poll Analysis API
    const updateAnalysis = async () => {
        try {
            const res = await fetch(API_ANALYSIS);
            if (!res.ok) throw new Error();
            const data = await res.json();
            
            if (data.status === 'no_data' || data.status === 'error') {
                thermalGradeEl.textContent = '?';
                thermalGradeEl.style.color = 'var(--text-secondary)';
                setScoreOffset(0);
                scoreDescEl.textContent = 'Awaiting Data';
                assessmentTextEl.textContent = data.message || 'Waiting for diagnostic records...';
                return;
            }

            thermalGradeEl.textContent = data.grade;
            thermalGradeEl.style.color = data.color;
            scoreRingFill.style.stroke = data.color;
            
            // Map letter grade to a percentage for the ring
            const gradeMap = { 'A+': 100, 'A': 92, 'B': 82, 'C': 72, 'D': 60, 'F': 35 };
            const percent = gradeMap[data.grade] || 50;
            setScoreOffset(percent);

            scoreDescEl.textContent = `Grade ${data.grade}`;
            assessmentTextEl.textContent = data.assessment;

            compIdleEl.textContent = data.avg_idle_temp ? `${data.avg_idle_temp.toFixed(1)}°C` : '--°C';
            compPeakEl.textContent = data.avg_load_temp ? `${data.avg_load_temp.toFixed(1)}°C` : 'N/A';
            compLoadEl.textContent = `${data.max_load.toFixed(1)}%`;
            
            const now = new Date();
            analysisTimeEl.textContent = `Updated ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
            
        } catch (err) {
            console.error("Error fetching thermal analysis: ", err);
        }
    };

    // Update History Chart Data
    const updateHistory = async () => {
        try {
            const res = await fetch(API_HISTORY);
            if (!res.ok) throw new Error();
            const data = await res.json();
            
            if (data.length === 0) return;

            const labels = data.map(d => {
                const t = new Date(d.timestamp);
                return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            });
            const temps = data.map(d => d.cpu_temp);
            const loads = data.map(d => d.cpu_usage);
            const scatterPoints = data.map(d => ({ x: d.cpu_usage, y: d.cpu_temp }));

            if (timelineChart && scatterChart) {
                // Update Timeline Chart
                timelineChart.data.labels = labels;
                timelineChart.data.datasets[0].data = temps;
                timelineChart.data.datasets[1].data = loads;
                timelineChart.update('none'); // Update without full animation for performance

                // Update Scatter Chart
                scatterChart.data.datasets[0].data = scatterPoints;
                scatterChart.update('none');
            } else {
                initCharts(data);
            }
        } catch (err) {
            console.error("Error updating charts: ", err);
        }
    };

    // Initialize Chart.js configuration
    const initCharts = (historyData) => {
        if (!window.Chart) return;

        // Custom chart styling
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = 'Inter';

        const labels = historyData.map(d => {
            const t = new Date(d.timestamp);
            return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        });
        const temps = historyData.map(d => d.cpu_temp);
        const loads = historyData.map(d => d.cpu_usage);

        // 1. Timeline Chart
        const ctxTimeline = timelineChartCanvas.getContext('2d');
        timelineChart = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'CPU Temperature (°C)',
                        data: temps,
                        borderColor: '#f43f5e',
                        backgroundColor: 'rgba(244, 63, 94, 0.04)',
                        yAxisID: 'y-temp',
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        tension: 0.25,
                        fill: true
                    },
                    {
                        label: 'CPU Utilization (%)',
                        data: loads,
                        borderColor: '#3b82f6',
                        backgroundColor: 'transparent',
                        yAxisID: 'y-load',
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        tension: 0.25
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            boxWidth: 12,
                            font: { family: 'Outfit', size: 12, weight: 500 },
                            color: '#e2e8f0'
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#ffffff',
                        borderColor: 'rgba(255,255,255,0.08)',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.02)' },
                        ticks: { color: '#64748b', maxTicksLimit: 8 }
                    },
                    'y-temp': {
                        type: 'linear',
                        position: 'left',
                        grid: { color: 'rgba(255,255,255,0.02)' },
                        ticks: { color: '#f43f5e' },
                        min: 20,
                        max: 100,
                        title: { display: true, text: 'Temp (°C)', color: '#f43f5e', font: { weight: 600 } }
                    },
                    'y-load': {
                        type: 'linear',
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#3b82f6' },
                        min: 0,
                        max: 100,
                        title: { display: true, text: 'Load (%)', color: '#3b82f6', font: { weight: 600 } }
                    }
                }
            }
        });

        // 2. Scatter Correlation Chart
        const ctxScatter = scatterChartCanvas.getContext('2d');
        const scatterPoints = historyData.map(d => ({ x: d.cpu_usage, y: d.cpu_temp }));

        scatterChart = new Chart(ctxScatter, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Thermal Response Profile',
                    data: scatterPoints,
                    backgroundColor: 'rgba(168, 85, 247, 0.4)',
                    borderColor: '#a855f7',
                    borderWidth: 1.5,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            boxWidth: 12,
                            font: { family: 'Outfit', size: 12, weight: 500 },
                            color: '#e2e8f0'
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        callbacks: {
                            label: function(context) {
                                return `Load: ${context.parsed.x.toFixed(1)}% | Temp: ${context.parsed.y.toFixed(1)}°C`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.02)' },
                        ticks: { color: '#64748b' },
                        min: 0,
                        max: 100,
                        title: { display: true, text: 'CPU Utilization (%)', color: '#94a3b8', font: { weight: 600 } }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.02)' },
                        ticks: { color: '#64748b' },
                        min: 20,
                        max: 100,
                        title: { display: true, text: 'CPU Temperature (°C)', color: '#94a3b8', font: { weight: 600 } }
                    }
                }
            }
        });
    };

    // Trigger Stress Test
    const startStressTest = async () => {
        try {
            const res = await fetch(API_STRESS_START, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ duration: 60 })
            });
            const data = await res.json();
            if (data.success) {
                stressActive = true;
                btnStressStart.classList.add('hidden');
                btnStressStop.classList.remove('hidden');
                stressStatusDisplay.classList.remove('hidden');
                stressTimeEl.textContent = '60';
                stressProgressFill.style.width = '100%';
            }
        } catch (err) {
            console.error("Failed to start stress test:", err);
        }
    };

    // Stop Stress Test
    const stopStressTest = async () => {
        try {
            const res = await fetch(API_STRESS_STOP, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                stressActive = false;
                btnStressStart.classList.remove('hidden');
                btnStressStop.classList.add('hidden');
                stressStatusDisplay.classList.add('hidden');
                // Refresh data immediately
                updateRealtime();
                setTimeout(() => {
                    updateAnalysis();
                    updateHistory();
                }, 1500);
            }
        } catch (err) {
            console.error("Failed to stop stress test:", err);
        }
    };

    // Event Listeners
    btnStressStart.addEventListener('click', startStressTest);
    btnStressStop.addEventListener('click', stopStressTest);

    // Chart Tabs Switcher
    btnShowHistory.addEventListener('click', () => {
        btnShowHistory.classList.add('active');
        btnShowScatter.classList.remove('active');
        timelineChartCanvas.classList.remove('hidden');
        scatterChartCanvas.classList.add('hidden');
        if (timelineChart) timelineChart.resize();
    });

    btnShowScatter.addEventListener('click', () => {
        btnShowScatter.classList.add('active');
        btnShowHistory.classList.remove('active');
        scatterChartCanvas.classList.remove('hidden');
        timelineChartCanvas.classList.add('hidden');
        if (scatterChart) scatterChart.resize();
    });

    // Initial setup and polling intervals
    updateRealtime();
    updateAnalysis();
    updateHistory();

    // 1-second interval for real-time widgets and process list
    setInterval(updateRealtime, 1000);

    // 5-second interval for analysis summary and metrics comparison
    setInterval(updateAnalysis, 5000);

    // 10-second interval for history charts updates
    setInterval(updateHistory, 10000);
});
