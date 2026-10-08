import os
import sys
import json
import zipfile
from pathlib import Path

def get_dir_summary(root_dir, max_depth=2, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = {'.venv', 'venv', '.git', '__pycache__', 'node_modules'}
    
    root = Path(root_dir)
    if not root.exists():
        return {"error": f"Path {root_dir} does not exist"}
    
    items = []
    
    def walk(current_dir, current_depth):
        try:
            entries = list(os.scandir(current_dir))
        except Exception as e:
            items.append({"path": str(current_dir), "error": str(e)})
            return
        
        for entry in entries:
            try:
                name = entry.name
                if entry.is_dir(follow_symlinks=False):
                    if name in exclude_dirs or name.startswith('.'):
                        items.append({"path": entry.path, "type": "dir", "excluded": True})
                        continue
                    items.append({"path": entry.path, "type": "dir", "depth": current_depth})
                    if current_depth < max_depth:
                        walk(entry.path, current_depth + 1)
                else:
                    stat = entry.stat()
                    items.append({
                        "path": entry.path,
                        "name": name,
                        "type": "file",
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "depth": current_depth
                    })
            except Exception as e:
                items.append({"path": getattr(entry, 'path', str(entry)), "error": str(e)})

    walk(root, 0)
    return items

if __name__ == "__main__":
    c_items = get_dir_summary(r"C:\Users\imgk3\Downloads", max_depth=2)
    print(f"C_Downloads items: {len(c_items)}")
    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\c_downloads_raw.json", "w", encoding="utf-8") as f:
        json.dump(c_items, f, indent=2)

    j_items = get_dir_summary(r"J:\My Drive\downloads", max_depth=2)
    print(f"J_Downloads items: {len(j_items)}")
    with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\j_downloads_raw.json", "w", encoding="utf-8") as f:
        json.dump(j_items, f, indent=2)
