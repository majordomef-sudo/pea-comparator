"""performance_monitor.py — Metrics de performance du pipeline Euromillions."""
import json, os, time, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = '/home/ubuntu/output/logs'
PERF_FILE = os.path.join(LOG_DIR, 'euromillions_perf_history.json')

class PerformanceMonitor:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.start_time = time.time()
        self.steps = {}
        self.current_step = None

    def start_step(self, name):
        self.current_step = name
        self.steps[name] = {'start': time.time()}

    def end_step(self):
        if self.current_step and self.current_step in self.steps:
            self.steps[self.current_step]['duration'] = time.time() - self.steps[self.current_step]['start']

    def get_report(self):
        total = time.time() - self.start_time
        mem = None
        try:
            r = subprocess.run(['ps', '-o', 'rss=', '-p', str(os.getpid())],
                              capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                mem = round(int(r.stdout.strip()) / 1024, 1)
        except: pass
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_duration': round(total, 3),
            'steps': {k: round(v.get('duration', 0), 3) for k, v in self.steps.items()},
            'memory_mb': mem
        }
        history = []
        if os.path.exists(PERF_FILE):
            try:
                with open(PERF_FILE) as f:
                    history = json.load(f)
            except: pass
        history.append(report)
        history = history[-30:]
        with open(PERF_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        return report
