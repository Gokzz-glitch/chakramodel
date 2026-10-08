import os

source = r'M:\chakramodel'

categories = {
    'virtual_env (.venv)': 0,
    'git_repository (.git)': 0,
    'agent_metadata (.agents, .claude, .bmad*)': 0,
    'cache (__pycache__, .pytest_cache)': 0,
    'datasets (data, dataset_yolo, datasets, etc.)': 0,
    'videos (video_testing, mp4/avi/mkv)': 0,
    'weights_checkpoints (weights, new_weights, checkpoints, pth/pt/bin/onnx)': 0,
    'kaggle_artifacts (kaggle_results, kaggle_upload, etc.)': 0,
    'outputs_archive (outputs, archive, etc.)': 0,
    'source_code_and_docs (src, scripts, tests, configs, docs, etc.)': 0,
    'root_large_archives (root zip files)': 0,
    'other': 0
}

cat_counts = {k: 0 for k in categories}
cat_sizes = {k: 0 for k in categories}

ext_sizes = {}
large_files = []

for root, dirs, files in os.walk(source):
    rel_root = os.path.relpath(root, source)
    for f in files:
        fp = os.path.join(root, f)
        rel_path = os.path.normpath(os.path.join(rel_root, f)) if rel_root != '.' else f
        try:
            sz = os.path.getsize(fp)
        except Exception:
            continue

        ext = os.path.splitext(f)[1].lower()
        ext_sizes[ext] = ext_sizes.get(ext, [0, 0])
        ext_sizes[ext][0] += 1
        ext_sizes[ext][1] += sz

        if sz >= 50 * 1024 * 1024:
            large_files.append((rel_path, sz))

        # Categorization logic
        parts = rel_path.split(os.sep)
        top = parts[0]

        if top == '.venv':
            cat = 'virtual_env (.venv)'
        elif top == '.git':
            cat = 'git_repository (.git)'
        elif top in ('.agents', '.claude', '.bmad-loop', '_bmad', '_bmad-output'):
            cat = 'agent_metadata (.agents, .claude, .bmad*)'
        elif top in ('__pycache__', '.pytest_cache') or any(p == '__pycache__' for p in parts):
            cat = 'cache (__pycache__, .pytest_cache)'
        elif top in ('data', 'dataset_yolo', 'dataset_yolo_fixed', 'datasets', 'raw_data', 'data_clean', 'data_processed'):
            cat = 'datasets (data, dataset_yolo, datasets, etc.)'
        elif top in ('video_testing',) or ext in ('.mp4', '.avi', '.mkv', '.mov'):
            cat = 'videos (video_testing, mp4/avi/mkv)'
        elif top in ('weights', 'new_weights', 'checkpoints') or ext in ('.pth', '.pt', '.bin', '.onnx', '.safetensors'):
            cat = 'weights_checkpoints (weights, new_weights, checkpoints, pth/pt/bin/onnx)'
        elif top.startswith('kaggle_') or top in ('Kaggle_Datasets_Upload',):
            cat = 'kaggle_artifacts (kaggle_results, kaggle_upload, etc.)'
        elif top in ('outputs', 'archive', 'runs', 'eval_results'):
            cat = 'outputs_archive (outputs, archive, etc.)'
        elif rel_root == '.' and ext in ('.zip', '.tar', '.gz'):
            cat = 'root_large_archives (root zip files)'
        elif top in ('src', 'scripts', 'tests', 'configs', 'docs', 'models', 'notebooks', 'benchmarks'):
            cat = 'source_code_and_docs (src, scripts, tests, configs, docs, etc.)'
        else:
            cat = 'other'

        cat_counts[cat] += 1
        cat_sizes[cat] += sz

print("=== M:\chakramodel Category Breakdown ===")
print(f"{'Category':<45} | {'Files':<8} | {'Size (MB)':<12} | {'Size (GB)':<10} | {'% of Total':<10}")
print("-" * 95)
total_files = sum(cat_counts.values())
total_sz = sum(cat_sizes.values())

for cat in categories:
    cnt = cat_counts[cat]
    sz = cat_sizes[cat]
    pct = (sz / total_sz * 100) if total_sz > 0 else 0
    print(f"{cat:<45} | {cnt:<8} | {sz / (1024*1024):<12.2f} | {sz / (1024**3):<10.3f} | {pct:<9.2f}%")
print("=" * 95)
print(f"{'TOTAL':<45} | {total_files:<8} | {total_sz / (1024*1024):<12.2f} | {total_sz / (1024**3):<10.3f} | 100.00%\n")

print("=== Top 15 File Extensions by Size ===")
print(f"{'Extension':<15} | {'Files':<8} | {'Size (MB)':<12} | {'Size (GB)':<10}")
print("-" * 55)
for ext, (cnt, sz) in sorted(ext_sizes.items(), key=lambda x: x[1][1], reverse=True)[:15]:
    print(f"{ext or '<no-ext>':<15} | {cnt:<8} | {sz / (1024*1024):<12.2f} | {sz / (1024**3):<10.3f}")
