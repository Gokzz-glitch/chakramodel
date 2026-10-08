import psutil
import time
import os
import sys

# Attempt to import GPUtil for VRAM usage. If not installed, it will be skipped.
try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False

# Thresholds
CPU_THRESHOLD = 90.0
RAM_THRESHOLD = 90.0
VRAM_THRESHOLD = 90.0

print(f"===========================================================")
print(f"          AGRIMATE V3: MULTI-PROCESS DYNAMIC THROTTLER     ")
print(f"===========================================================")
print(f"Monitoring Thresholds:")
print(f" - CPU  > {CPU_THRESHOLD}%")
print(f" - RAM  > {RAM_THRESHOLD}%")
print(f" - VRAM > {VRAM_THRESHOLD}%")
print(f"")
print(f"[INFO] The throttler will dynamically slow down target processes")
print(f"       (python, node) via micro-suspensions without stopping them.")
print(f"       Press Ctrl+C to exit.")
print(f"===========================================================\n")

def check_vram():
    if not HAS_GPUTIL:
        return 0.0
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            # Percentage of VRAM used (0.0 to 1.0) -> multiply by 100
            return max([gpu.memoryUtil for gpu in gpus]) * 100
    except Exception:
        pass
    return 0.0

def slow_down_processes():
    my_pid = os.getpid()
    target_names = ['python', 'node', 'python.exe', 'node.exe']
    affected_pids = []

    # 1. Target processes and Suspend them
    for p in psutil.process_iter(['pid', 'name']):
        try:
            pid = p.info['pid']
            name = p.info['name'].lower()
            if pid == my_pid:
                continue
            
            # If the process matches our targets
            if any(target in name for target in target_names):
                p_obj = psutil.Process(pid)
                p_obj.suspend()
                affected_pids.append(p_obj)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # 2. Let the hardware cool down for a short duration while processes are "slowed" 
    time.sleep(2.0)
    
    # 3. Resume all suspended processes so they "never stop" doing their work
    for p_obj in affected_pids:
        try:
            p_obj.resume()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def main():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            vram = check_vram()

            issues = []
            if cpu > CPU_THRESHOLD:
                issues.append(f"CPU: {cpu}%")
            if ram > RAM_THRESHOLD:
                issues.append(f"RAM: {ram}%")
            if vram > VRAM_THRESHOLD:
                issues.append(f"VRAM: {vram:.1f}%")

            if issues:
                print(f"[⚡ STRESS DETECTED] {', '.join(issues)}. Slowing down processes...")
                slow_down_processes()
            else:
                # Normal operation, sleep a bit before checking again
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n[INFO] Exiting hardware monitor.")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Monitor loop encountered an error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
