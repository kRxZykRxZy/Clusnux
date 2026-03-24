import psutil
from typing import Dict


def collect_system_metrics() -> Dict:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()._asdict()
    disk = psutil.disk_usage('/')._asdict()
    net = psutil.net_io_counters(pernic=True)
    return {
        "task": "metrics",
        "cpu_percent": cpu,
        "memory": mem,
        "disk": disk,
        "network": {k: v._asdict() for k, v in net.items()}
    }

