import json
from pathlib import Path

with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\categorized_inventory.json", "r", encoding="utf-8") as f:
    cat = json.load(f)

other_nb = cat.get("other_notebooks", [])
print(f"Total other notebooks: {len(other_nb)}")

for item in other_nb:
    p = item["path"]
    name = Path(p).name
    size = item["size"]
    print(f"  {size:>10,d} bytes  {name}")
