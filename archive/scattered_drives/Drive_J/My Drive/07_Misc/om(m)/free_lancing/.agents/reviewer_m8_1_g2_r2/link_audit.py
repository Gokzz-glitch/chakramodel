import re
from pathlib import Path

templates = ["general", "cafe", "transport", "salon", "retail", "fitness", "clinic"]

for t in templates:
    t_dir = Path("templates") / t
    h_text = (t_dir / "index.html").read_text(encoding="utf-8")
    
    tel_matches = re.findall(r'href=["\'](tel:[^"\']*)["\']', h_text)
    mailto_matches = re.findall(r'href=["\'](mailto:[^"\']*)["\']', h_text)
    maps_matches = re.findall(r'href=["\']([^"\']*maps[^"\']*)["\']', h_text)
    
    print(f"\n[{t}] Link href analysis:")
    print(f"  tel: {tel_matches}")
    print(f"  mailto: {mailto_matches}")
    print(f"  maps: {maps_matches}")
