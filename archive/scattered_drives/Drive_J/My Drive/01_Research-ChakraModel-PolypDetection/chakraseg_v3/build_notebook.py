"""Builds chakraseg_v3_kaggle.ipynb from the tested chakraseg_v3.py + adapter (nbformat v4 JSON)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "chakraseg_v3.py")).read()
adp = open(os.path.join(HERE, "adapter_chakraseg_v3.py")).read()


def md(t):
    return dict(cell_type="markdown", metadata={}, source=t.strip("\n").splitlines(True))


def code(t):
    return dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=t.strip("\n").splitlines(True))


cells = []
cells.append(md(r"""
# ChakraSeg-v3 on Kaggle: foundation-encoder experiments R9 / R10 (29 Sep 2026)

This notebook runs the experiments from `deep_part1_ablation_meta_analysis_2026-09-29` and
`large_models_architectures_datasets_2026-09-29`. All logic lives in `chakraseg_v3.py`, which was
smoke-tested on CPU with synthetic data. The notebook only configures and schedules runs.

**Before you start**
1. Settings → **Accelerator: GPU T4 ×2**, **Internet: ON** (timm/HF weights, SAM2 checkpoint).
2. **Add Data:** the leakbench datasets that hold the manifests and images (`v2.csv`, `r6_mixneg.csv`, …).
3. Edit the **CONFIG** cell: manifest paths, `SHARD` (0–3, one per teammate account) and `TIERS`.
4. Run once with `SMOKE = True` (about 3 minutes: tiny random models, 3 iterations). Only then set `SMOKE = False`.

**What gets written:** `/kaggle/working/runs_v3/<config>_s<seed>/` containing `results.json`,
`per_image.csv`, `log.json`, `config.json` and `best.pt` (trainable weights only, a few MB for LoRA or
frozen runs). Also `summary.md` for the whole folder and `v3_results.zip` (no weights) to hand back.

**Rules carried over from the project:** grouped split, 3 seeds, ClinicDB column flagged as
contaminated, paired-bootstrap CIs before claiming any gain (Part 1 §1 noise floor: ≥3 ETIS / ≥2 ColonDB),
and false alarms scored on polyp-free frames for every arm.
"""))

cells.append(code(r"""
# 1. Environment
import os, sys, json, glob, time, shlex, subprocess, zipfile
try:
    print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv'], capture_output=True, text=True).stdout)
except FileNotFoundError:
    print('no nvidia-smi (CPU session)')
import torch
print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '| gpus', torch.cuda.device_count())
try:
    import timm
    from packaging.version import Version
    if Version(timm.__version__) < Version('1.0.20'):   # DINOv3 models need >= 1.0.20
        raise ImportError
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'timm>=1.0.20'], check=True)
    import importlib, timm; importlib.reload(timm)
print('timm', timm.__version__)
"""))

cells.append(code("%%writefile chakraseg_v3.py\n" + src))
cells.append(code("%%writefile adapter_chakraseg_v3.py\n" + adp))

cells.append(code(r"""
# 2. CONFIG: edit this cell
MANIFESTS = {
    'v2':  '/kaggle/input/chakra-leakbench-v1/manifests/v2.csv',          # EDIT: grouped split, no negatives
    'mix': '/kaggle/input/chakra-leakbench-v1/manifests/r6_mixneg.csv',   # EDIT: + 20% HK/PolypGen negatives
}
ROOTS    = ['/kaggle/input']      # every attached dataset is searched; paths in the manifest may be relative
PATH_MAP = []                     # e.g. ['M:/chakramodelpro/leakbench/=/kaggle/input/chakra-leakbench-v1/']
OUT      = '/kaggle/working/runs_v3'
SEEDS    = [42, 43, 44]
SHARD, N_SHARDS = 0, 4            # teammate k runs SHARD=k (0..3); jobs are dealt round-robin
TIERS    = [1]                    # 1 = decisive comparisons, 2 = more backbones, 3 = ablations
SESSION_HOURS = 11.5              # Kaggle hard limit is 12 h; no new run starts after this minus PER_RUN_HOURS
PER_RUN_HOURS = 2.5               # each run stops training at this cap and still tests its best checkpoint
SMOKE    = True                   # True = 3-minute pipeline check with tiny random models. Then set False.

# auto-locate manifests if the paths above are wrong
for k, p in list(MANIFESTS.items()):
    if not os.path.isfile(p):
        name = os.path.basename(p)
        hits = glob.glob(f'/kaggle/input/**/{name}', recursive=True)
        print(f'[config] {k}: {p} not found; candidates: {hits[:3]}')
        if hits:
            MANIFESTS[k] = hits[0]
print(json.dumps(MANIFESTS, indent=1))
os.makedirs(f'{OUT}/logs', exist_ok=True)
"""))

cells.append(code(r"""
# 3. Manifest audit: split inventory, path resolution, negatives, train/val group overlap (must be 0)
for k, p in MANIFESTS.items():
    print('=' * 20, k, p)
    cmd = [sys.executable, 'chakraseg_v3.py', 'audit', '--manifest', p, '--roots', *ROOTS]
    if PATH_MAP: cmd += ['--path-map', *PATH_MAP]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-4000:], r.stderr[-2000:])
# Check the printout: missing_img / missing_mask must be 0; split names must include train, val,
# test_* and (for 'mix') training negatives; negatives in test must be split names starting with 'neg'.
"""))

cells.append(code(r"""
# 4. Experiment grid (see Part 2 doc for the rationale of each arm)
L14 = '--arch v3vit --backbone vit_large_patch14_dinov2.lvd142m --img-size 392'
GRID = {
  # ---- tier 1: the decisive comparisons --------------------------------------------------------
  'R9a_vitL16in21k_full':  (1, 'v2',  '--arch v3vit --backbone vit_large_patch16_384.augreg_in21k_ft_in1k --img-size 384 '
                                      '--freeze full --llrd 0.8 --lr 1e-4 --drop-path 0.2 --cnn-branch none --presence 0 --bs 4 --accum 4'),
  'R9c_dinov2L_frozen':    (1, 'v2',  f'{L14} --freeze frozen --cnn-branch none --presence 0 --lr 2e-4 --bs 8 --accum 2'),
  'R10b_dinov2L_lora_cnn': (1, 'v2',  f'{L14} --freeze lora --cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 0 --lr 2e-4 --bs 8 --accum 2'),
  'R10a_v3_mix':           (1, 'mix', f'{L14} --freeze lora --cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 1 --gate hard --lr 2e-4 --bs 8 --accum 2'),
  # ---- tier 2: more backbones --------------------------------------------------------------------
  'R9b_dinov2L_full':      (2, 'v2',  f'{L14} --freeze full --llrd 0.8 --lr 1e-4 --drop-path 0.2 --cnn-branch none --presence 0 --bs 4 --accum 4'),
  'R9d_sam2unet':          (2, 'v2',  '--arch sam2unet --img-size 352 --ms-rates 1,1.25 --epochs 20 --lr 1e-3 --wd 5e-4 --aux-w 1.0 --bs 12 --accum 1 --presence 0'),
  'R9d_sam2unet_mix':      (2, 'mix', '--arch sam2unet --img-size 352 --ms-rates 1,1.25 --epochs 20 --lr 1e-3 --wd 5e-4 --aux-w 1.0 --bs 12 --accum 1 --presence 0'),
  'R10c_cnxT_dinov3_mix':  (2, 'mix', '--arch v3conv --backbone convnext_tiny.dinov3_lvd1689m --img-size 352 --freeze full --lr 2e-4 --lr-backbone 1e-4 --presence 1 --bs 16 --accum 1'),
  'R10d_cnxL_dinov3_mix':  (2, 'mix', '--arch v3conv --backbone convnext_large.dinov3_lvd1689m --img-size 352 --freeze full --lr 2e-4 --lr-backbone 5e-5 --presence 1 --bs 8 --accum 2'),
  # ---- tier 3: ablations of the v3 design --------------------------------------------------------
  'R10a_nopres_mix':       (3, 'mix', f'{L14} --freeze lora --cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 0 --lr 2e-4 --bs 8 --accum 2'),
  'R10a_posonly_mix':      (3, 'mix', f'{L14} --freeze lora --cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 1 --mask-loss-on-neg 0 --lr 2e-4 --bs 8 --accum 2'),
  'R10e_dinov3L_lora_cnn': (3, 'v2',  '--arch v3vit --backbone vit_large_patch16_dinov3.lvd1689m --img-size 384 --freeze lora '
                                      '--cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 0 --lr 2e-4 --bs 8 --accum 2'),
  # Part 3 (test-set anatomy): unseen sets are 2.5-4.7x blurrier and lower-contrast than Kvasir at network resolution
  'R10f_v3_degaug_mix':    (3, 'mix', f'{L14} --freeze lora --cnn-branch resnet34.a1_in1k --xattn-fuse 1 --presence 1 --gate hard '
                                      '--deg-aug 0.5 --lab-aug 0.3 --lr 2e-4 --bs 8 --accum 2'),
  'R10g_cnxT_degaug_mix':  (3, 'mix', '--arch v3conv --backbone convnext_tiny.dinov3_lvd1689m --img-size 352 --freeze full --lr 2e-4 '
                                      '--lr-backbone 1e-4 --presence 1 --deg-aug 0.5 --lab-aug 0.3 --bs 16 --accum 1'),
}
SMOKE_ARGS = ['--pretrained', '0', '--epochs', '1', '--max-iters', '3', '--dim', '64', '--img-size', '112',
              '--backbone', 'vit_small_patch14_dinov2', '--cnn-branch', 'resnet18', '--bs', '2', '--accum', '1']
selected = [(n, v) for n, v in GRID.items() if v[0] in TIERS]
if SMOKE:   # one v3vit and one v3conv config, 1 seed: exercises data, training, gating, testing, summary
    selected = [('SMOKE_v3vit', (0, 'mix', '--arch v3vit --presence 1 --freeze lora')),
                ('SMOKE_v3conv', (0, 'mix', '--arch v3conv --presence 1 --freeze full'))]
jobs = [(n, s, v[1], v[2]) for n, v in selected for s in (SEEDS if not SMOKE else [42])]
jobs = [j for i, j in enumerate(jobs) if i % N_SHARDS == SHARD] if not SMOKE else jobs
print(f'{len(jobs)} jobs for shard {SHARD}:')
for j in jobs: print('  ', j[0], 'seed', j[1], 'on', j[2])

if any(n.startswith('R9d') for n, _ in selected) and not SMOKE:   # SAM2-UNet setup
    if not os.path.isdir('SAM2-UNet'):
        subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/WZH0120/SAM2-UNet.git'], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'hydra-core==1.3.2', 'iopath'], check=True)
    if not os.path.isfile('sam2_hiera_large.pt'):
        subprocess.run(['wget', '-q', 'https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_large.pt'], check=True)
"""))

cells.append(code(r"""
# 5. Runner: one job per GPU in parallel, resume-safe (skips runs that already have results.json)
from collections import deque
def launch(job, gpu):
    name, seed, mkey, extra = job
    run = f'{name}_s{seed}'
    if os.path.isfile(f'{OUT}/{run}/results.json'):
        print('[skip]', run); return None
    cmd = [sys.executable, 'chakraseg_v3.py', 'train', '--manifest', MANIFESTS[mkey], '--roots', *ROOTS,
           '--out', OUT, '--run-name', run, '--seed', str(seed), '--max-epochs-time', str(PER_RUN_HOURS)]
    if PATH_MAP: cmd += ['--path-map', *PATH_MAP]
    cmd += shlex.split(extra)
    if 'sam2unet' in extra: cmd += ['--sam2unet-repo', 'SAM2-UNet', '--hiera-ckpt', 'sam2_hiera_large.pt']
    if SMOKE:
        cmd += SMOKE_ARGS + (['--backbone', 'convnext_tiny', '--img-size', '128'] if 'v3conv' in extra else [])
    env = dict(os.environ)
    if gpu is not None: env['CUDA_VISIBLE_DEVICES'] = str(gpu)
    log = open(f'{OUT}/logs/{run}.log', 'w')
    print(f'[start] {run} on gpu {gpu}')
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)

gpus = list(range(torch.cuda.device_count())) or [None]
queue, running, t0 = deque(jobs), {}, time.time()
while queue or running:
    for g in gpus:
        if g not in running and queue:
            if (time.time() - t0) / 3600 > SESSION_HOURS - PER_RUN_HOURS:
                print('[runner] session budget reached; not starting', [q[0] for q in queue]); queue.clear(); break
            job = queue.popleft(); p = launch(job, g)
            if p is not None: running[g] = (job, p, time.time())
    for g, (job, p, ts) in list(running.items()):
        if p.poll() is not None:
            run = f'{job[0]}_s{job[1]}'
            status = 'ok' if p.returncode == 0 else f'FAILED rc={p.returncode}'
            print(f'[done] {run} {status} in {(time.time() - ts) / 60:.0f} min')
            if p.returncode != 0:
                print(open(f'{OUT}/logs/{run}.log').read()[-3000:])
            del running[g]
    time.sleep(10)
print('[runner] finished in %.1f h' % ((time.time() - t0) / 3600))
"""))

cells.append(code(r"""
# 6. Summary: seed mean ± sd per split, cost, paired bootstrap against a reference configuration
REF = 'SMOKE_v3vit' if SMOKE else 'R9a_vitL16in21k_full'   # compare everything against the fixed-recipe ViT-L
r = subprocess.run([sys.executable, 'chakraseg_v3.py', 'summary', '--out', OUT, '--ref', REF], capture_output=True, text=True)
print(r.stdout[-12000:], r.stderr[-2000:])
"""))

cells.append(code(r"""
# 7. Operating points for runs with a presence head: detection at false-alarm budgets
# Thresholds are tuned on TUNE split(s) only and reported on the others. Pick a polyp-free split you do
# not report as a headline (e.g. a held-out PolypGen split). Here: the first neg_* split found.
for pi in sorted(glob.glob(f'{OUT}/*/per_image.csv')):
    import pandas as pd
    d = pd.read_csv(pi, usecols=['split', 'neg'])
    negs = sorted(d[d.neg.astype(str).str.lower().isin(['true', '1'])].split.unique())
    if not negs: continue
    print('=' * 10, os.path.basename(os.path.dirname(pi)))
    r = subprocess.run([sys.executable, 'chakraseg_v3.py', 'ops', '--per-image', pi, '--tune-splits', negs[0]],
                       capture_output=True, text=True)
    print(r.stdout[-3000:], r.stderr[-1000:])
"""))

cells.append(code(r"""
# 7b. Optional, no retraining: does a larger TEST resolution rescue small polyps? (Part 3)
# ETIS frames are 1225x966; at 392 px a third of its polyps are < 3 ViT tokens across.
RES_TEST = [] if SMOKE else ['R10a_v3_mix_s42']          # runs to re-score
for run in RES_TEST:
    for size in (392, 518):
        if not os.path.isdir(f'{OUT}/{run}'): continue
        r = subprocess.run([sys.executable, 'chakraseg_v3.py', 'eval', '--run', f'{OUT}/{run}', '--manifest', MANIFESTS['mix'],
                            '--roots', *ROOTS, '--img-size', str(size), '--tag', f'res{size}'] + (['--path-map', *PATH_MAP] if PATH_MAP else []),
                           capture_output=True, text=True)
        print(run, size, r.stdout[-1500:], r.stderr[-500:])
"""))

cells.append(code(r"""
# 8. Package results (no weights) to download / upload back to the project
zp = '/kaggle/working/v3_results.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in glob.glob(f'{OUT}/**/*', recursive=True):
        if f.endswith(('.json', '.csv', '.md', '.log')):
            z.write(f, os.path.relpath(f, '/kaggle/working'))
print(zp, os.path.getsize(zp) // 1024, 'KB')
"""))

cells.append(md(r"""
### Add a new test set later (Kvasir-Instrument, BUET, REAL-Colon negatives) without retraining
Build a CSV with columns `image,mask,split`. Polyp splits must be named `test_<name>`, and polyp-free splits
`neg_<name>` with an empty mask column. Then run:
```
python chakraseg_v3.py eval --run /kaggle/working/runs_v3/R10a_v3_mix_s42 --manifest new_tests.csv --roots /kaggle/input
```
It writes `results_new_tests.json` and `per_image_new_tests.csv` inside the run folder.

### Score a run with the leakbench harness
`CHAKRASEG_RUN=<run dir>` plus `adapter_chakraseg_v3.py`. This follows the same `load(device) → predict(bgr)`
interface as `adapters/chakraguard.py`.
"""))

nb = dict(cells=cells, metadata=dict(kernelspec=dict(display_name="Python 3", language="python", name="python3"),
                                     language_info=dict(name="python")), nbformat=4, nbformat_minor=5)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "chakraseg_v3_kaggle.ipynb")
json.dump(nb, open(out, "w"), indent=1)
print("wrote", out, len(cells), "cells")
