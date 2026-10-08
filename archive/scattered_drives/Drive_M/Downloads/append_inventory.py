import os

inventory_file = r"C:\Users\imgk3\.gemini\antigravity\brain\ed10122d-e091-4566-9916-252437fa3b14\system_wide_inventory.md"

summary = """

## Cloud Storage (Google Drive - I:\ and J:\)

An expanded deep scan across the Google Drive virtual mounts (`I:\` and `J:\`) revealed a massive repository of raw dataset files related to polyp detection.

> [!WARNING]
> Due to the extreme volume (over **640,000 files**), these have not been individually listed here. Instead, here is a summary of the contents found on the cloud drives:

| File Type | Count | Total Size (MB) | Probable Content |
|---|---|---|---|
| **.jpg** | 394,048 | 46,671 MB | Raw colonoscopy frames / Endoscopy images |
| **.txt** | 117,726 | 65 MB | YOLO bounding box labels |
| **.png** | 98,889 | 7,352 MB | Segmentation masks / GT masks |
| **.mp4** | 637 | 87,732 MB | Raw colonoscopy videos |
| **.md** | 14,061 | 121 MB | Dataset documentation / Readmes |
| **.py** | 3,214 | 23 MB | Distributed processing scripts |

*Note: These files are safely stored in Google Drive and do not need to be manually copied to the `D:\` backup drive.*
"""

try:
    with open(inventory_file, 'a', encoding='utf-8') as f:
        f.write(summary)
    print("Inventory updated with Google Drive summary.")
except Exception as e:
    print(f"Error: {e}")
