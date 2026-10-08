import importlib.metadata

dists = sorted([d.metadata['Name'] for d in importlib.metadata.distributions()])
print(f"Total installed packages: {len(dists)}")

keywords = ['ocr', 'vision', 'cv', 'image', 'layout', 'text', 'doc', 'pdf', 'paddle', 'easy', 'tess', 'torch', 'model', 'onnx', 'gemini', 'google', 'anthropic', 'open']
matched = [d for d in dists if any(k in d.lower() for k in keywords)]
print(f"Matched packages ({len(matched)}):")
for m in matched:
    try:
        ver = importlib.metadata.version(m)
        print(f"  {m}: {ver}")
    except Exception:
        print(f"  {m}")
