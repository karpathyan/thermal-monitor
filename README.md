# AeroTherm 🌡️💨

AeroTherm is a lightweight, real-time CPU thermal diagnostic dashboard and background monitor. Designed for Linux systems (especially Dell motherboards using the `dell_smm` driver), it monitors CPU temperatures, overall & per-core utilization, RAM usage, active processes, and fan speeds, logging history to help you evaluate the effectiveness of your cooling setup.

It includes an integrated **Thermal Stress Tester** that allows you to safely stress your CPU to 100% load for 60 seconds directly from the browser, helping you see how effectively your cooling fan handles peak heat and how quickly it recovers.

---

## ✨ Features

* **Real-time Gauges**: Visual circular indicators for CPU Temperature, CPU Utilization, and Fan RPM.
* **Dynamic Fan Rotation**: A custom fan icon in the UI that spins at a speed proportional to the actual fan RPM (e.g. static at 0 RPM, fast spin at 3000 RPM).
* **Thermal Diagnostic Report**: An automated grading system (A+ through F) evaluating cooling efficiency, average idle/load temps, and safety margins.
* **Integrated Stress Tester**: A safe, multi-processed CPU stress utility that runs for 60 seconds (or manual abort) to test heat dissipation under load.
* **Process Monitor**: Real-time list of top CPU-consuming processes.
* **Timeline & Correlation Charts**:
  * **Load & Temp Timeline**: Linear progression of CPU load vs temp over time.
  * **Thermal Curve (Correlation)**: A scatter plot of Temperature vs Load, mapping the system's thermal resistance profile.
* **Zero Dependencies (Browser)**: Client-side logic runs on vanilla HTML5/CSS3/JS, with Chart.js loaded via CDN. No `npm install` needed!

---

## 🚀 Getting Started

### 📋 Prerequisites

The server runs on Python 3 and requires the `psutil` package to query system sensors.

Install `psutil` using pip:
```bash
pip install psutil
```

### 🏃 Running the Monitor

1. Clone this repository (or download the files).
2. Start the AeroTherm monitor server:
   ```bash
   python3 monitor_server.py
   ```
3. Open your browser and navigate to:
   **[http://localhost:8888](http://localhost:8888)**

---

## 🛠️ Project Structure

* `monitor_server.py`: The Python background sensor daemon and HTTP/REST server.
* `index.html`: The glassmorphic dashboard layout.
* `index.css`: Dashboard styling, custom gradients, neon shadows, and fan animations.
* `index.js`: State updates, radial gauges mathematics, Chart.js integrations, and event handlers.
* `.gitignore`: Excludes log data (`thermal_log.csv`) and Python cache files from version control.

---

## 📜 License

This project is licensed under the MIT License. Feel free to use, modify, and distribute it!
