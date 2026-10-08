import json

with open("colab.ipynb", "r") as f:
    data = json.load(f)

for cell in data["cells"]:
    if cell["cell_type"] == "code":
        sources = cell["source"]
        for i, line in enumerate(sources):
            if "repo.remotes.origin.pull()" in line:
                sources[i] = "            repo.git.fetch('--all')\n            repo.git.reset('--hard', 'origin/main')\n"

with open("colab.ipynb", "w") as f:
    json.dump(data, f, indent=2)

print("Updated colab.ipynb to fetch and reset hard.")
