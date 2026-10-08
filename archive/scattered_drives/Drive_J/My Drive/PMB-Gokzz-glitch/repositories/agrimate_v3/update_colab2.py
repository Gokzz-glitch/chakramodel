import json

with open("colab.ipynb", "r") as f:
    data = json.load(f)

for cell in data["cells"]:
    if cell["cell_type"] == "code":
        sources = cell["source"]
        for i, line in enumerate(sources):
            if "repo.remotes.origin.pull()" in line:
                sources[i] = "            repo.git.pull('--rebase')\n"

with open("colab.ipynb", "w") as f:
    json.dump(data, f, indent=2)

print("Updated git pull to use rebase in colab.ipynb")
