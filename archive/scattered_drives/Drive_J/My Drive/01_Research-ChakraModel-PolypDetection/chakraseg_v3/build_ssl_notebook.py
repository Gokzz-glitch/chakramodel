"""Builds chakraseg_ssl_kaggle.ipynb (Part 4): in-domain pool -> ExPLoRA-style SSL pilot -> downstream screen ->
3-seed confirmation, plus the noisy-student pseudo-label route. Embeds chakraseg_v3.py, build_ssl_pool.py and
ssl_continue.py so the notebook is self-contained."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
emb = {f: open(os.path.join(HERE, f)).read() for f in ("chakraseg_v3.py", "build_ssl_pool.py", "ssl_continue.py")}


def md(t):
    return dict(cell_type="markdown", metadata={}, source=t.strip("\n").splitlines(True))


def code(t):
    return dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=t.strip("\n").splitlines(True))


cells = [md(r"""
# ChakraSeg-v3 · Part 4: in-domain pretraining pilot and noisy-student pseudo-labels (29 Sep 2026)

Two routes to more in-domain signal. Each is judged by a downstream check with 3 seeds and paired bootstrap:

* **Route A: ExPLoRA-style continued DINOv2 pretraining.** It runs on a deduplicated, leakage-checked pool of
  unlabeled colonoscopy frames. The last 2 blocks are unfrozen, LoRA sits on the others, a fresh DINO head is trained
  with an EMA teacher, and the calibrated blur/compression degradation is part of the augmentations. Checkpoints are
  exported as plain timm weights for `chakraseg_v3.py --backbone-ckpt`.
* **Route B: noisy-student pseudo-labels.** A finished R10a run labels the same pool. Only confident positives and
  confident negatives are kept, as a random sample capped per class. A student is then retrained on real + pseudo
  labels, and the result is compared with R10f, which has the same augmentations and no pseudo-labels.

**Settings: GPU T4 ×2, Internet ON.** Attach:
1. the unlabeled sources (HyperKvasir unlabeled images, LDPolypVideo unannotated videos, optionally LDPolyp labelled frames);
2. the leakbench dataset (manifests + images), because every non-train image in `TEST_MANIFESTS` is removed from the pool;
3. the main notebook's output folder, which holds the R10a teacher and any finished R10b/R10f reference runs.

**Session plan (Kaggle stops a session at 12 h; all times are estimates, not measured):**

| session | cells | wall time |
|---|---|---|
| 1 | A1 pool (~1 h, CPU) → A2 SSL on GPU 0 (capped at 6 h) while B1 pseudo-labels on GPU 1 (≤3 h) → A3 frozen screen (≤5 arms on 2 GPUs, ~1–1.5 h) | ~8–8.5 h |
| 2 | set `S1` to session 1's output → A3 re-reads its results → QUEUE runs A4 (R10b_ssl × 3 seeds) and B2 (R11 × 3 seeds) on 2 GPUs | ~8 h if the R10b/R10f reference runs are attached; otherwise the time guard stops it and a 3rd session resumes via `PREV_OUTPUTS` |

Run `SMOKE=True` first on any accelerator. It checks every cell end to end in a few minutes with tiny random
models. Then set `SMOKE=False` and use **Save Version → Save & Run All** so the session keeps running with the tab closed.
"""),
         code(r"""
# 0. Environment
import os, sys, json, glob, time, shutil, subprocess
try:
    print(subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv'], capture_output=True, text=True).stdout)
except FileNotFoundError:
    print('no nvidia-smi (CPU session)')
import torch
print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '| gpus', torch.cuda.device_count())
try:
    import timm
    from packaging.version import Version
    if Version(timm.__version__) < Version('1.0.20'):
        raise ImportError
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'timm>=1.0.20'], check=True)
    import importlib, timm; importlib.reload(timm)
print('timm', timm.__version__)
"""),
         code("%%writefile chakraseg_v3.py\n" + emb["chakraseg_v3.py"]),
         code("%%writefile build_ssl_pool.py\n" + emb["build_ssl_pool.py"]),
         code("%%writefile ssl_continue.py\n" + emb["ssl_continue.py"]),
         code(r"""
# 1. CONFIG (edit)
SMOKE = True
S1 = ''            # session 2+: the attached OUTPUT of session 1 (e.g. '/kaggle/input/chakra-ssl-session1'); '' = session 1
PREV_OUTPUTS = []  # session 3+: attached outputs of later sessions; their finished runs are reused, not retrained
# session 1 builds the pool, runs SSL + pseudo-labels and the frozen screen; session 2 runs the 3-seed queue
RUN = dict(A1=not S1, A2=not S1, B1=not S1, A3=True, A4=bool(S1), B2=bool(S1), QUEUE=bool(S1))
SOURCES = {      # name -> folder of images and/or videos (EDIT to your attached datasets; missing ones are skipped)
    'hk_unlabeled': '/kaggle/input/hyper-kvasir-unlabeled/unlabeled-images',   # 99,417 images (upper + lower GI)
    'ld_unannot':   '/kaggle/input/ldpolypvideo/videos_without_polyp',         # 103 unannotated videos, 861,400 frames
    'ld_labeled':   '/kaggle/input/ldpolypvideo/labeled_frames',               # optional; capped below
}
SRC_CAPS = {'ld_labeled': 4000}          # random sample per source (consecutive video frames are near-duplicates)
TEST_MANIFESTS = ['/kaggle/input/chakra-leakbench-v1/manifests/v2.csv',          # every non-train row is excluded
                  '/kaggle/input/chakra-leakbench-v1/manifests/r6_mixneg.csv']   # add ANY manifest you will test on
MANIFEST_PATH_MAP = []                    # as in the main notebook, e.g. ['M:/chakramodelpro/leakbench/=/kaggle/input/chakra-leakbench-v1/']
ROOTS = ['/kaggle/input']
REF_RUNS = '/kaggle/input/chakra-v3-runs'            # main-notebook runs: R10a_v3_mix_s*, R10b_dinov2L_lora_cnn_s*, R10f_v3_degaug_mix_s*
TEACHER_RUN = f'{REF_RUNS}/R10a_v3_mix_s42'          # Route B teacher (needs the presence head)
BACKBONE = 'vit_large_patch14_dinov2.lvd142m'
PILOT_ITERS, PILOT_BS, PILOT_HOURS = 8000, 32, 6.0   # 256k samples ≈ 2 passes over a ~125k pool
PER_RUN_HOURS = 2.5                                  # training cap per supervised run (same as the main notebook)
SEEDS = [42, 43, 44]
SESSION_HOURS = 11.5                                 # no queued run starts after SESSION_HOURS - PER_RUN_HOURS
PSEUDO_CAPS = (3000, 3000)                           # max pseudo positives, negatives kept by B1 (random sample)
NEG_SHARE = None     # B2: negative share of the training rows; None = same share as the labelled train split (r6: 20 %)
SESSION_T0 = time.time()

for i, p in enumerate(TEST_MANIFESTS):                # auto-locate manifests if the paths above are wrong
    if not os.path.isfile(p):
        hits = glob.glob(f'/kaggle/input/**/{os.path.basename(p)}', recursive=True)
        print(f'[config] {p} not found; candidates: {hits[:3]}')
        if hits: TEST_MANIFESTS[i] = hits[0]
MAN_V2, MAN_MIX = TEST_MANIFESTS[0], TEST_MANIFESTS[1]

W = '/kaggle/working'
BASE = S1 or W
POOL, SSL_OUT, PSEUDO = f'{BASE}/ssl_pool', f'{BASE}/ssl_vitl', f'{BASE}/pseudo'
PMAP = MANIFEST_PATH_MAP + ([f'{W}/={S1}/'] if S1 else [])   # + session-1 absolute paths -> attached copy
PATH_MAP = ['--path-map', *PMAP] if PMAP else []
N_GPU = max(1, torch.cuda.device_count())
CNN = 'resnet34.a1_in1k'
SMALL = []
if SMOKE:   # tiny random models, 1 seed, a few iterations: checks every code path, not accuracy
    RUN = {k: True for k in RUN}
    SEEDS, PER_RUN_HOURS, CNN = [42], 0.05, 'resnet18'
    SMALL = ['--pretrained', '0', '--backbone', 'vit_small_patch14_dinov2', '--img-size', '112', '--dim', '64',
             '--epochs', '1', '--max-iters', '2', '--bs', '2', '--accum', '1', '--workers', '0']
os.makedirs(f'{W}/logs', exist_ok=True)


def run(cmd, log=None, gpu=None):
    cmd = [str(c) for c in cmd]
    env = dict(os.environ, **({'CUDA_VISIBLE_DEVICES': str(gpu)} if gpu is not None else {}))
    print('>>', ' '.join(cmd)[:400], flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if log:
        open(log, 'w').write(r.stdout + r.stderr)
    print((r.stdout[-4000:] + r.stderr[-2500:]).strip(), flush=True)
    if r.returncode:
        print(f'!! exit code {r.returncode}' + (f' (full log: {log})' if log else ''))
    return r.returncode


def run_parallel(jobs):
    # jobs: list of (name, cmd, log); one job per GPU at a time; returns {name: exit code}
    free, live, codes, jobs = list(range(N_GPU)), [], {}, list(jobs)
    while jobs or live:
        if jobs and (time.time() - SESSION_T0) / 3600 > SESSION_HOURS - PER_RUN_HOURS:
            print(f'session time guard: {len(jobs)} jobs NOT started (rerun with PREV_OUTPUTS to resume):', [j[0] for j in jobs])
            jobs = []
        while jobs and free:
            name, cmd, log = jobs.pop(0); g = free.pop(0)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g))
            print(f'>> [gpu{g}] {name}', flush=True)
            live.append((subprocess.Popen([str(c) for c in cmd], stdout=open(log, 'w'), stderr=subprocess.STDOUT, env=env), g, name, log))
        time.sleep(2 if SMOKE else 20)
        for item in list(live):
            p, g, name, log = item
            if p.poll() is not None:
                live.remove(item); free.append(g); codes[name] = p.returncode
                print(f'<< [gpu{g}] {name}: exit {p.returncode}' + ('' if p.returncode == 0 else f'  -> tail {log}:\n' + open(log).read()[-1500:]), flush=True)
    return codes


def link_done(out, configs):
    # symlink finished runs (main-notebook references, or earlier sessions of this notebook) into `out`,
    # so they are not retrained and `summary` pairs them with the new arm
    os.makedirs(out, exist_ok=True)
    for src_dir in [REF_RUNS] + [f'{p}/{os.path.basename(out)}' for p in PREV_OUTPUTS]:
        for c in configs:
            for s in SEEDS:
                src, dst = f'{src_dir}/{c}_s{s}', f'{out}/{c}_s{s}'
                if os.path.isfile(f'{src}/results.json') and not os.path.exists(dst):
                    os.symlink(src, dst); print('finished run linked:', dst)


print(dict(SMOKE=SMOKE, S1=S1 or None, N_GPU=N_GPU, POOL=POOL, SSL_OUT=SSL_OUT, PSEUDO=PSEUDO, RUN=RUN))
"""),
         code(r"""
# A1. Pool: decode videos at 1 fps, drop uninformative frames, dedupe, REMOVE anything near a test/val image
if RUN['A1'] and not S1:
    srcs = [f'--src={k}={v}' for k, v in SOURCES.items() if os.path.exists(v)]
    print('sources found:', srcs, '| missing:', [k for k, v in SOURCES.items() if not os.path.exists(v)])
    cmd = [sys.executable, 'build_ssl_pool.py', *srcs, '--out', POOL, '--fps', '1', '--roots', *ROOTS]
    if MANIFEST_PATH_MAP: cmd += ['--path-map', *MANIFEST_PATH_MAP]
    cmd += [f'--src-cap={k}={v}' for k, v in SRC_CAPS.items() if k in SOURCES and os.path.exists(SOURCES[k])]
    for m in TEST_MANIFESTS:
        if os.path.isfile(m): cmd += ['--test-manifest', m]
    if SMOKE: cmd += ['--max-per-source', '200', '--sharp-min', '1']   # synthetic frames are smooth (real ones: >= 68)
    run(cmd, f'{W}/logs/A1_pool.log')
rep = f'{POOL}/pool_report.json'
print(open(rep).read() if os.path.isfile(rep) else 'no pool yet')
"""),
         code(r"""
# A2. ExPLoRA-style continued DINO pretraining on GPU 0; checkpoints every 2000 iterations for downstream selection.
#     With 2 GPUs and B1 enabled it runs in the background so B1 can pseudo-label on GPU 1 at the same time.
A2_PROC = None
if RUN['A2'] and not S1:
    cmd = [sys.executable, 'ssl_continue.py', '--pool', f'{POOL}/pool.csv', '--roots', POOL, '--backbone', BACKBONE,
           '--unfreeze', '2', '--lora-r', '32', '--iters', PILOT_ITERS, '--bs', PILOT_BS, '--save-every', '2000',
           '--out', SSL_OUT, '--max-hours', PILOT_HOURS]
    if SMOKE:
        cmd = [sys.executable, 'ssl_continue.py', '--pool', f'{POOL}/pool.csv', '--roots', POOL,
               '--backbone', 'vit_small_patch14_dinov2', '--pretrained', '0', '--iters', '10', '--bs', '4',
               '--gsize', '112', '--lsize', '56', '--n-local', '2', '--head-warmup', '4', '--warmup', '4',
               '--save-every', '5', '--out', SSL_OUT, '--workers', '0', '--out-dim', '512']
    log = f'{W}/logs/A2_ssl.log'
    if RUN['B1'] and N_GPU > 1 and os.path.isdir(TEACHER_RUN):
        A2_PROC = subprocess.Popen([str(c) for c in cmd], stdout=open(log, 'w'), stderr=subprocess.STDOUT,
                                   env=dict(os.environ, CUDA_VISIBLE_DEVICES='0'))
        print('A2 running in the background on GPU 0; log:', log)
    else:
        run(cmd, log, gpu=0)
        print(sorted(glob.glob(f'{SSL_OUT}/backbone_merged_*.pth')))
"""),
         code(r"""
# B1. Noisy-student pseudo-labels from the R10a teacher (strict thresholds, random sample capped per class)
if RUN['B1'] and not S1:
    if os.path.isdir(TEACHER_RUN):
        cmd = [sys.executable, 'chakraseg_v3.py', 'pseudo', '--run', TEACHER_RUN, '--manifest', f'{POOL}/pool.csv',
               '--roots', POOL, *ROOTS, *PATH_MAP, '--out-dir', PSEUDO, '--pos-tau', '0.9', '--peak-tau', '0.9', '--neg-tau', '0.05',
               '--uncertain-max', '0.3', '--max-pos', PSEUDO_CAPS[0], '--max-neg', PSEUDO_CAPS[1],
               '--merge-with', MAN_MIX, '--tta', '1', '--seed', '0']
        if SMOKE:   # untrained teacher: accept everything so the merge and the retraining path are exercised
            cmd += ['--pos-tau', '0', '--peak-tau', '0', '--neg-tau', '1', '--uncertain-max', '1e9', '--workers', '0']
        run(cmd, f'{W}/logs/B1_pseudo.log', gpu=1 if N_GPU > 1 else 0)
    else:
        print('B1 skipped: TEACHER_RUN not found ->', TEACHER_RUN)
st = f'{PSEUDO}/pseudo_stats.json'
print(open(st).read() if os.path.isfile(st) else 'no pseudo-labels yet')
"""),
         code(r"""
# B1b. Pseudo-label QA: yield per source and two contact sheets (green = pseudo-mask). Look at them before B2:
#      instruments, bubbles, stool or specular glare outlined as polyps mean the thresholds are too loose.
qa = f'{PSEUDO}/pseudo.csv'
if os.path.isfile(qa):
    import csv, random as _r, cv2, numpy as np
    from collections import Counter
    fix = lambda p: p if os.path.exists(p) or not S1 else p.replace(f'{W}/', f'{S1}/', 1)
    rows = list(csv.DictReader(open(qa)))
    src = lambda p: os.path.basename(p).rsplit('_', 1)[0]
    print('pseudo-positives by source:', dict(Counter(src(r['image']) for r in rows if r['mask'])))
    print('pseudo-negatives by source:', dict(Counter(src(r['image']) for r in rows if not r['mask'])))

    def sheet(rs, fn, n=48, t=160):
        rs = _r.Random(0).sample(rs, min(n, len(rs)))
        tiles = []
        for r in rs:
            im = cv2.imread(fix(r['image']))
            if im is None:
                continue
            im = cv2.resize(im, (t, t))
            mk = cv2.imread(fix(r['mask']), 0) if r['mask'] else None
            if mk is not None:
                mk = cv2.resize(mk, (t, t), interpolation=cv2.INTER_NEAREST)
                cs, _ = cv2.findContours((mk > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(im, cs, -1, (0, 255, 0), 2)
            tiles.append(im)
        if not tiles:
            return
        while len(tiles) % 8:
            tiles.append(np.zeros((t, t, 3), np.uint8))
        cv2.imwrite(fn, np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, len(tiles), 8)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print('wrote', fn)
        try:
            from IPython.display import Image, display
            display(Image(fn))
        except Exception:
            pass

    sheet([r for r in rows if r['mask']], f'{W}/pseudo_qa_positives.jpg')
    sheet([r for r in rows if not r['mask']], f'{W}/pseudo_qa_negatives.jpg')
else:
    print('no pseudo-labels to check')
"""),
         code(r"""
# A3. Downstream screen: the frozen-backbone R9c recipe with each SSL checkpoint vs the original DINOv2. Only the decoder
#     trains, so this measures feature quality. Selection uses VALIDATION (meta.best_val) only, never test.
BEST_CKPT = ''
if RUN['A3']:
    if A2_PROC is not None:
        print('waiting for A2 ...', flush=True); A2_PROC.wait()
        print('A2 exit', A2_PROC.returncode, '\n', open(f'{W}/logs/A2_ssl.log').read()[-2500:])
    OUT_A = f'{W}/runs_ssl'
    if S1 and os.path.isdir(f'{S1}/runs_ssl'):
        shutil.copytree(f'{S1}/runs_ssl', OUT_A, dirs_exist_ok=True)
    ckpts = sorted(glob.glob(f'{SSL_OUT}/backbone_merged_*.pth'))
    arms = [('R9c_orig', '')] + [(f'R9c_ssl{os.path.basename(c)[16:22]}', c) for c in ckpts]
    jobs = []
    for name, ck in arms:
        if os.path.isfile(f'{OUT_A}/{name}_s42/results.json'):
            continue
        cmd = [sys.executable, 'chakraseg_v3.py', 'train', '--manifest', MAN_V2, '--roots', *ROOTS, *PATH_MAP,
               '--out', OUT_A, '--run-name', f'{name}_s42', '--seed', '42', '--arch', 'v3vit', '--backbone', BACKBONE,
               '--img-size', '392', '--freeze', 'frozen', '--cnn-branch', 'none', '--presence', '0', '--lr', '2e-4',
               '--bs', '8', '--accum', '2', '--epochs', '20', '--max-epochs-time', min(1.0, PER_RUN_HOURS)]
        if ck: cmd += ['--backbone-ckpt', ck]
        cmd += SMALL
        jobs.append((name, cmd, f'{W}/logs/A3_{name}.log'))
    run_parallel(jobs)
    val = {}
    for name, ck in arms:
        rj = f'{OUT_A}/{name}_s42/results.json'
        if os.path.isfile(rj):
            val[name] = (json.load(open(rj))['meta']['best_val'], ck)
    for n, (v, ck) in sorted(val.items(), key=lambda kv: -kv[1][0]):
        print(f'{n:22s} best val gated mDice {v:.4f}')
    base = val.get('R9c_orig', (None, ''))[0]
    cands = sorted((v, ck) for n, (v, ck) in val.items() if ck)
    if base is not None and cands and cands[-1][0] > base:
        BEST_CKPT = cands[-1][1]
    if SMOKE and not BEST_CKPT and cands:
        BEST_CKPT = cands[-1][1]   # smoke only: exercise A4 even though random models decide nothing
    print('BEST_CKPT =', BEST_CKPT or '(no SSL checkpoint beats the original on VAL: Route A stops here)')
    run([sys.executable, 'chakraseg_v3.py', 'summary', '--out', OUT_A, '--ref', 'R9c_orig'], f'{W}/logs/A3_summary.log')
"""),
         code(r"""
# A4. Confirmation under the real recipe: R10b (LoRA + ResNet-34 branch), best SSL checkpoint vs original, 3 seeds.
#     Finished R10b_dinov2L_lora_cnn_s* runs from the main notebook are linked, not retrained.
JOBS, OUT_B, OUT_C = [], f'{W}/runs_ssl_r10b', f'{W}/runs_noisystudent'
R10B = ['--arch', 'v3vit', '--backbone', BACKBONE, '--img-size', '392', '--freeze', 'lora', '--cnn-branch', CNN,
        '--xattn-fuse', '1', '--presence', '0', '--lr', '2e-4', '--bs', '8', '--accum', '2']
if RUN['A4'] and BEST_CKPT:
    link_done(OUT_B, ['R10b_dinov2L_lora_cnn', 'R10b_ssl'])
    for s in SEEDS:
        for name, ck in (('R10b_dinov2L_lora_cnn', ''), ('R10b_ssl', BEST_CKPT)):
            if os.path.exists(f'{OUT_B}/{name}_s{s}/results.json'):
                continue
            cmd = [sys.executable, 'chakraseg_v3.py', 'train', '--manifest', MAN_V2, '--roots', *ROOTS, *PATH_MAP,
                   '--out', OUT_B, '--run-name', f'{name}_s{s}', '--seed', s, *R10B, '--max-epochs-time', PER_RUN_HOURS]
            if ck: cmd += ['--backbone-ckpt', ck]
            cmd += SMALL
            JOBS.append((f'A4_{name}_s{s}', cmd, f'{W}/logs/A4_{name}_s{s}.log'))
print(len(JOBS), 'A4 jobs queued')
"""),
         code(r"""
# B2. Noisy student: R10f recipe (R10a + Part-3 degradation/colour augmentation) on real + pseudo labels, vs R10f itself.
#     The reference has the same augmentations, so the difference isolates the pseudo-labels.
R10F = ['--arch', 'v3vit', '--backbone', BACKBONE, '--img-size', '392', '--freeze', 'lora', '--cnn-branch', CNN,
        '--xattn-fuse', '1', '--presence', '1', '--gate', 'hard', '--deg-aug', '0.5', '--lab-aug', '0.3',
        '--lr', '2e-4', '--bs', '8', '--accum', '2']
merged = f'{PSEUDO}/merged_manifest.csv'


def balance(src_csv, out_csv):
    # keep the labelled negative share: drop random pseudo-negatives beyond it (R2: a heavier negative share raised
    # ETIS misses), so R11 differs from R10f in the number of examples, not in the class mix
    import random as _r, pandas as pd
    sys.path.insert(0, os.getcwd()); import chakraseg_v3 as C
    m = pd.read_csv(src_csv, dtype=str, keep_default_na=False)
    sc, mc = C._pick(m.columns, C.SPLIT_COLS), C._pick(m.columns, C.MASK_COLS)
    sp, has = m[sc].str.lower(), (m[mc].str.strip() != '')
    real_pos, real_neg = int(((sp == 'train') & has).sum()), int(((sp == 'train') & ~has).sum())
    ps_pos, ps_neg = m.index[(sp == 'train_pseudo') & has], list(m.index[(sp == 'train_pseudo') & ~has])
    share = NEG_SHARE if NEG_SHARE is not None else real_neg / max(1, real_pos + real_neg)
    allowed = max(0, int(share / (1 - share) * (real_pos + len(ps_pos))) - real_neg)
    _r.Random(0).shuffle(ps_neg)
    m.drop(index=ps_neg[allowed:]).to_csv(out_csv, index=False)
    print(dict(real_pos=real_pos, real_neg=real_neg, pseudo_pos=len(ps_pos), pseudo_neg=min(allowed, len(ps_neg)),
               pseudo_neg_dropped=max(0, len(ps_neg) - allowed), neg_share=round(share, 3)))
    return out_csv


if RUN['B2'] and os.path.isfile(merged):
    merged = balance(merged, f'{W}/merged_balanced.csv')
    link_done(OUT_C, ['R10f_v3_degaug_mix', 'R11_noisystudent'])
    for s in SEEDS:
        arms = (('R10f_v3_degaug_mix', MAN_MIX, ['--roots', *ROOTS, *PATH_MAP]),
                ('R11_noisystudent', merged, ['--roots', '/kaggle/input', W, *PATH_MAP, '--train-splits', 'train', 'train_pseudo']))
        for name, man, extra in arms:
            if os.path.exists(f'{OUT_C}/{name}_s{s}/results.json'):
                continue
            cmd = [sys.executable, 'chakraseg_v3.py', 'train', '--manifest', man, *extra, '--out', OUT_C,
                   '--run-name', f'{name}_s{s}', '--seed', s, *R10F, '--max-epochs-time', PER_RUN_HOURS]
            cmd += SMALL
            JOBS.append((f'B2_{name}_s{s}', cmd, f'{W}/logs/B2_{name}_s{s}.log'))
elif RUN['B2']:
    print('B2 skipped: no merged manifest at', merged)
print(len(JOBS), 'jobs queued in total')
"""),
         code(r"""
# QUEUE. Run every queued A4/B2 job, one per GPU, then the paired summaries
if RUN['QUEUE'] and JOBS:
    t0 = time.time(); codes = run_parallel(JOBS)
    print(f'queue finished in {(time.time() - t0) / 3600:.2f} h; failures:', {k: v for k, v in codes.items() if v})
for out, ref in ((OUT_B, 'R10b_dinov2L_lora_cnn'), (OUT_C, 'R10f_v3_degaug_mix')):
    if glob.glob(f'{out}/*/results.json'):
        run([sys.executable, 'chakraseg_v3.py', 'summary', '--out', out, '--ref', ref], f'{W}/logs/summary_{os.path.basename(out)}.log')
"""),
         md(r"""
**Decision gate (Part 1 §1 noise floor; per-image SD ≈ 0.30).** Keep an SSL checkpoint or the pseudo-label student only if
**both** hold against its twin (R10b original for A4, R10f for B2):
1. the paired bootstrap CI excludes 0;
2. the gain is **≥ +3 ETIS or ≥ +2 ColonDB** Dice points.

A clear Dice gain under blur at an equal false-alarm rate (Part 3 F2; `eval` on the blurred copies) is also enough.
Otherwise stop the route. In EndoDINO's own ViT-B table, in-domain SSL at matched model size gave **no** gain
(0.895 vs 0.896 ImageNet). The prior for Route A is therefore weak, and the gate exists to stop cheaply.

**A2 health check:** in `logs/A2_ssl.log`, `teacher_entropy` rising to ln(8192) ≈ 9.0 means uniform collapse.
`teacher_batch_entropy` falling to the level of `teacher_entropy` (both small) means every frame maps to one prototype.
Either one: stop and rerun with a lower `--lr`.

**Keep between sessions:** the notebook output (`/kaggle/working`) holds the pool (≈8–11 GB, estimated), the SSL
checkpoints (1.2 GB each in fp32), the pseudo-labels and all runs. Attach it to session 2 as a dataset and set `S1`.
""")]
nb = dict(cells=cells, metadata=dict(kernelspec=dict(display_name="Python 3", language="python", name="python3"),
                                     language_info=dict(name="python")), nbformat=4, nbformat_minor=5)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "chakraseg_ssl_kaggle.ipynb")
json.dump(nb, open(out, "w"), indent=1)
print("wrote", out, len(cells), "cells")
