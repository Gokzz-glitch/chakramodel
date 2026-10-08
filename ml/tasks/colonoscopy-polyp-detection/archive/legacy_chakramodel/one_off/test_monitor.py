import sys
sys.path.insert(0, 'src')
from hardware_monitor import HardwareMonitor
import time

m = HardwareMonitor()
m.start()
time.sleep(2)
s = m.status_dict()
print(f"Phase:           {s['phase']}")
print(f"GPU fraction:    {s['gpu_vram_fraction']:.0%} (~{s['gpu_vram_fraction']*4:.2f} GB)")
print(f"Warmup remain:   {s['warmup_remaining_s']:.0f}s")
print(f"Ramp starts at:  {m.gpu_rampup_start}s")
print(f"Full boost at:   {m.warmup_seconds}s")
print(f"Plugged in:      {s['plugged_in']}")
m.stop()
print("OK")
