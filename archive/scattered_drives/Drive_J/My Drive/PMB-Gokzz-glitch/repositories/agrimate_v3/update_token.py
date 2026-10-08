import json

with open("colab.ipynb", "r") as f:
    data = json.load(f)

for cell in data["cells"]:
    if cell["cell_type"] == "code":
        sources = cell["source"]
        for i, line in enumerate(sources):
            if "3AkyCcPqqi5r2xkaQeImQ5SmihU_2BAvPSijE4aUG9Gg7EnMY" in line:
                sources[i] = line.replace("3AkyCcPqqi5r2xkaQeImQ5SmihU_2BAvPSijE4aUG9Gg7EnMY", "3AoPwhrtqkccgECfaxkehffIARc_36xfCkzFWrw4SAGRzMADR")

with open("colab.ipynb", "w") as f:
    json.dump(data, f, indent=2)

print("Updated Ngrok Token!")
