import psutil
import socket
import platform
import json
import requests
import time
import subprocess

CONTROL_SERVER_URL = "http://10.5.0.2:5000/report"  # Replace with your control server's IP and port

# Load monitored services from a config file
def load_monitored_services():
    try:
        with open("monitored_services.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_monitored_services(services):
    with open("monitored_services.json", "w") as f:
        json.dump(services, f)

monitored_services = load_monitored_services()

def get_system_data():
    data = {
        "hostname": socket.gethostname(),
        "cpu_info": get_cpu_info(),
        "cpu_usage": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_total": psutil.virtual_memory().total,
        "ram_used": psutil.virtual_memory().used,
        "ram_free": psutil.virtual_memory().available,
        "disk_usage": disk_usage(),
        "net_sent": psutil.net_io_counters().bytes_sent,
        "net_received": psutil.net_io_counters().bytes_recv,
        "services": check_all_services(),
        "drives_health": check_all_drives_health(),
        "timestamp": time.time()
    }
    return data

def get_cpu_info():
    if platform.system() == "Linux":
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":")[1].strip()
    else:
        return platform.processor()

def disk_usage():
    partitions = psutil.disk_partitions()
    partition_usage = {}
    
    for partition in partitions:
        if partition.device.startswith('/dev/') and not any(kw in partition.mountpoint for kw in ['snap', 'loop', 'var']):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partition_usage[partition.mountpoint] = {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                }
            except PermissionError:
                continue
    
    return partition_usage

def check_all_services():
    status = {}
    for service in monitored_services:
        status[service] = check_service_status(service)
    return status

def check_service_status(service_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == service_name:
            return True
    return False

def check_all_drives_health():
    drives = list_all_drives()
    health = {}
    for drive in drives:
        health[drive] = check_drive_health(drive)
    return health

def list_all_drives():
    partitions = psutil.disk_partitions(all=False)
    drives = [partition.device for partition in partitions if partition.device.startswith('/dev/')]
    return drives

def check_drive_health(drive):
    try:
        result = subprocess.run(['smartctl', '-H', drive], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "PASSED" in result.stdout:
            return "PASSED"
        elif "FAILED" in result.stdout:
            return "FAILED"
        else:
            return "UNKNOWN"
    except Exception as e:
        return f"ERROR: {str(e)}"

def report_to_control_server():
    while True:
        data = get_system_data()
        try:
            response = requests.post(CONTROL_SERVER_URL, json=data)
            print(f"Reported to control server: {response.status_code}")
        except Exception as e:
            print(f"Failed to report: {str(e)}")
        time.sleep(2)  # Report every 60 seconds

if __name__ == "__main__":
    report_to_control_server()
