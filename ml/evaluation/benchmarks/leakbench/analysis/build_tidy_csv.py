"""Builds two CSVs under leakbench/analysis/:
  leakbench_results_tidy.csv        one row per (experiment, model, seed, eval dataset, metric) + source file path
  leakbench_dataset_result_map.csv  one row per dataset: disk count, disk path, and the results mapped to it
Run on the device:  python3 analysis/build_tidy_csv.py"""
import json, glob, os, re, collections, numpy as np, pandas as pd
H = os.path.expanduser('~/mnt/chakramodelpro/leakbench'); os.chdir(H)
WIN = r'M:\chakramodelpro\leakbench'
def win(rel): return WIN + '\\' + rel.replace('/', '\\')

DS = {  # internal split name -> (display name, group)
 'test_kvasir': ('Kvasir (test)', 'polyp test'), 'test_clinicdb': ('CVC-ClinicDB (test)', 'polyp test'),
 'test_colondb': ('CVC-ColonDB (test)', 'polyp test'), 'test_etis': ('ETIS (test)', 'polyp test'),
 'test_cvc300': ('CVC-300 (test)', 'polyp test'), 'test_clinicfold': ('CVC-ClinicDB 5-fold held-out fold', 'polyp CV'),
 'neg_polypgen': ('PolypGen negatives (4,275)', 'polyp-free'), 'neg_hyperkvasir': ('HyperKvasir negatives (2,947)', 'polyp-free'),
 'neg_pg_heldout': ('PolypGen held-out sequences (2,404)', 'polyp-free'), 'neg_thirdsource': ('Third-source negatives PICCOLO+PolypGen single (168)', 'polyp-free'),
 'neg_piccolo': ('PICCOLO negatives', 'polyp-free'), 'neg_polypgen_single': ('PolypGen single-frame negatives', 'polyp-free'),
 'test_piccolo_all': ('PICCOLO (all)', 'external polyp'), 'test_polypdb_WLI': ('PolypDB WLI', 'external polyp'), 'test_polypdb_NBI': ('PolypDB NBI', 'external polyp'),
 'test_polypdb_BLI': ('PolypDB BLI', 'external polyp'), 'test_polypdb_FICE': ('PolypDB FICE', 'external polyp'), 'test_polypdb_LCI': ('PolypDB LCI', 'external polyp'),
}
for i in range(1, 7): DS[f'test_polypgen_C{i}'] = (f'PolypGen centre C{i}', 'external polyp')
MET = [('mDice', 'mDice'), ('mIoU', 'mIoU'), ('MAE', 'MAE'), ('mDice_small', 'mDice_small_polyps(<5% frame)'),
       ('false_alarm_rate@0.0', 'FA_rate(any fg px)'), ('false_alarm_rate@0.001', 'FA_rate(fg>0.1% frame)'),
       ('false_alarm_rate@0.01', 'FA_rate(fg>1% frame)'), ('mean_fg_frac', 'mean_fg_frac')]
rows = []
def add(exp, desc, model, trained_on, neg_pct, seed, split, n, metric, value, src, kind='results.json', extra=''):
    nm, grp = DS.get(split, (split, 'other'))
    rows.append(dict(experiment=exp, experiment_desc=desc, model=model, trained_on=trained_on, neg_pct_in_training=neg_pct, seed=seed,
                     eval_dataset=nm, dataset_group=grp, eval_n=n, metric=metric, value=value, source_file=win(src), source_kind=kind, note=extra))

def ingest(path, exp, desc, model, trained_on, neg_pct, seed, extra=''):
    d = json.load(open(path))
    for t, v in d['tests'].items():
        for k, lab in MET:
            if k in v and v[k] is not None:
                add(exp, desc, model, trained_on, neg_pct, seed, t, v.get('n'), lab, v[k], path, extra=extra)
    return d

# E1 (v2 split, 0% negatives) -- training runs
for f in sorted(glob.glob('runs/v2__*/results.json')):
    d = ingest(f, 'E1', 'Group-aware split v2, 0% negatives', json.load(open(f))['model'], 'v2.csv', 0, json.load(open(f))['seed'])
    add('E1', 'Group-aware split v2, 0% negatives', d['model'], 'v2.csv', 0, d['seed'], 'val', d['val_n'], 'best_val_mDice', d['best_val_mDice'], f)
    add('E1', 'Group-aware split v2, 0% negatives', d['model'], 'v2.csv', 0, d['seed'], 'run', None, 'fps_bs1_fp16', d['latency']['fps_bs1_fp16'], f)
    add('E1', 'Group-aware split v2, 0% negatives', d['model'], 'v2.csv', 0, d['seed'], 'run', None, 'params_M', d['params'] / 1e6, f)
# E1 checkpoints scored on HyperKvasir negatives
for f in sorted(glob.glob('r2/ev_e1_hk/*.json')):
    if 'per_image' in f: continue
    d = json.load(open(f)); ingest(f, 'E1', 'Group-aware split v2, 0% negatives', d['model'], d['trained_on'], 0, d['seed'], extra='HyperKvasir negatives scored in R2 eval-only pass')
# E2 (v1 random split) -- training runs
for f in sorted(glob.glob('r2/runs_e2/*/results.json')):
    d = ingest(f, 'E2', 'v1 random split (val shares video frames with train), 0% negatives', json.load(open(f))['model'], 'std (v1 random split)', 0, json.load(open(f))['seed'])
    add('E2', 'v1 random split (val shares video frames with train), 0% negatives', d['model'], 'std (v1 random split)', 0, d['seed'], 'val', d['val_n'], 'best_val_mDice', d['best_val_mDice'], f)
# E3 ClinicDB 5-fold CV
for f in sorted(glob.glob('runs_e3/leak_*/results.json')):
    d = json.load(open(f)); m = re.match(r'leak_f(\d)_(grouped|random)', d['tag'])
    ingest(f, 'E3', 'ClinicDB 5-fold CV, video-grouped vs random folds', d['model'], f'fold {m.group(1)} ({m.group(2)})', 0, d['seed'], extra=f'cv_mode={m.group(2)}; fold={m.group(1)}')
    add('E3', 'ClinicDB 5-fold CV, video-grouped vs random folds', d['model'], f'fold {m.group(1)} ({m.group(2)})', 0, d['seed'], 'val', d['val_n'], 'best_val_mDice', d['best_val_mDice'], f, extra=f'cv_mode={m.group(2)}; fold={m.group(1)}')
# E4 / E4b negatives in training, S2 external transfer
PCT = {'v2': 0, 'e4_negtrain': 20, 'e4b_negtrain50': 50}
for f in sorted(glob.glob('r2/ev_e4/*.json')):
    if 'per_image' in f: continue
    d = json.load(open(f)); pfx = d['tag'].split('__')[0]
    ingest(f, 'E4', 'Polyp-free negatives added to training (20% / 50%)', d['model'], d['trained_on'], PCT[pfx], d['seed'])
for f in sorted(glob.glob('r2/ev_s2/*.json')):
    if 'per_image' in f: continue
    d = json.load(open(f)); pfx = d['tag'].split('__')[0]
    ingest(f, 'S2', 'External transfer of E1/E4/E4b checkpoints (PICCOLO, PolypGen C1-6, PolypDB)', d['model'], d['trained_on'], PCT[pfx], d['seed'])
# R5
for f in sorted(glob.glob('r5/runs_r5/*/results.json')):
    d = json.load(open(f)); cell = d['tag'].split('__')[1]
    ingest(f, 'R5', 'Encoder x decoder ablation (0% negatives)', cell, d['manifest'], 0, d['seed'])
    add('R5', 'Encoder x decoder ablation (0% negatives)', cell, d['manifest'], 0, d['seed'], 'val', d['val_n'], 'best_val_mDice', d['best_val_mDice'], f)
# R5 corner cells that come from E1 (unet_r34 / seg_mit_b2 / fpn_pvtv2b2), re-labelled to the R5 grid names
CORNER = {'unet_r34': 'unet_r34', 'segformer_b2': 'seg_mit_b2', 'fpn_pvtv2b2': 'fpn_pvtv2b2'}
for f in sorted(glob.glob('runs/v2__*/results.json')):
    d = json.load(open(f))
    if d['model'] in CORNER:
        ingest(f, 'R5', 'Encoder x decoder ablation (0% negatives)', CORNER[d['model']], d['manifest'], 0, d['seed'], extra='corner cell taken from E1 run')
for f in sorted(glob.glob('r2/ev_e1_hk/*.json')):          # HyperKvasir scores of the same three corner cells
    if 'per_image' in f: continue
    d = json.load(open(f))
    if d['model'] in CORNER:
        ingest(f, 'R5', 'Encoder x decoder ablation (0% negatives)', CORNER[d['model']], d['trained_on'], 0, d['seed'], extra='corner cell taken from E1 run; HyperKvasir pass')
# R6
for f in sorted(glob.glob('r6/*/results.json')):
    d = json.load(open(f)); arm = 'pgneg' if 'pgneg' in d['tag'] else 'mixneg'
    ingest(f, 'R6', 'Negative diversity: same 20% budget from 1 vs 2 centres', d['model'], d['manifest'], 20, d['seed'], extra=f'arm={arm}')
# Third-party / pretrained models (values read from notebook outputs, xlsx or docx)
TP = 'Third-party pretrained eval'
def tp(model, ds, n, vals, src, kind, note=''):
    for k, v in vals.items():
        if v is not None: add('TP', TP, model, 'authors\' pretrained weights', None, None, ds, n, k, v, src, kind, note)
def xl(path, col_ds, groups):
    df = pd.read_excel(path)
    out = {}
    for g in df[col_ds].unique():
        s = df[df[col_ds] == g]; out[g] = (len(s), float(s[[c for c in df.columns if c.lower() == 'dice'][0]].mean()), float(s[[c for c in df.columns if c.lower() == 'iou'][0]].mean()))
    return out
B = '_wcmp/thambi_req/'
r = pd.read_excel(B + 'pranet tf/author & og/kvasir_per_image_metrics.xlsx')
tp('PraNet-TF (ResNet50)', 'Kvasir-SEG (full 1000)', len(r), dict(mDice=r.dice.mean(), mIoU=r.iou.mean(), MAE=r.mae.mean()), B + 'pranet tf/author & og/kvasir_per_image_metrics.xlsx', 'per-image xlsx (mean recomputed)', 'pranet-tf.ipynb; scored on all 1000 Kvasir-SEG images, not the 100-image test split')
r = pd.read_excel(B + 'pranet v2/og/per_image_metrics.xlsx')
for g, s in r.groupby('dataset'):
    tp('PraNet-V2', f'{g} (full)', len(s), dict(mDice=s.dice.mean(), mIoU=s.iou.mean()), B + 'pranet v2/og/per_image_metrics.xlsx', 'per-image xlsx (mean recomputed)', 'pranetv2.ipynb; FAILED RUN, near-zero Dice indicates a pipeline fault')
r = pd.read_excel(B + 'sepnet/og/all_images_metrics (2).xlsx')
for g, s in r.groupby('Dataset'):
    tp('SEPNet (PVTv2-B2)', {'datasets_Kvasir-SEG': 'Kvasir-SEG (full 1000)', 'datasets_PNG': 'CVC-ClinicDB PNG (full 612)', 'datasets_TIF': 'CVC-ClinicDB TIF (same 612 frames)'}[g], len(s), dict(mDice=s.Dice.mean(), mIoU=s.IoU.mean()), B + 'sepnet/og/all_images_metrics (2).xlsx', 'per-image xlsx (mean recomputed)', 'sepnet (3).ipynb')
P19 = B + 'pranet-19/og/pranetcod.docx'
for ds, n, dice, iou, mae in [('Kvasir-SEG (full 1000)', 1000, .971087, .947707, .007606), ('CVC-ClinicDB (test)', 62, .901158, .853311, .009518), ('CVC-300 (test)', 60, .886418, .813726, .007998),
                              ('CVC-ColonDB (test)', 380, .710237, .639516, .036182), ('ETIS (test)', 196, .613152, .548978, .016374)]:
    tp('PraNet-19 (official)', ds, n, dict(mDice=dice, mIoU=iou, MAE=mae), P19, 'docx printed table', 'pranetcod.ipynb saves masks only; metrics are in this docx')
N12 = 'external_eval/models/pranetf/pranet (2).ipynb'
tp('PraNet-TF (ResNet50)', 'Kvasir-SEG (full 1000)', 1000, dict(mDice=.9191, mIoU=.8700, MAE=.0294), N12, 'notebook output', 'pranet (2).ipynb')
tp('PraNet-TF (ResNet50)', 'LDPolypVideo (INVALID: identical to Kvasir row)', 1000, dict(mDice=.9191, mIoU=.8700, MAE=.0294), N12, 'notebook output', 'identical to 4 decimals to the Kvasir row => same data scored twice')
tp('CompNet (5.01M)', 'Kvasir-SEG (full 1000)', 1000, dict(mDice=.8631, mIoU=.7822), 'external_eval/models/compnet/compnet-testing-24-09-26-9-40.ipynb', 'notebook output', 'precision 0.8738, recall 0.8804, micro Dice 0.8838')
# Third-party Kvasir-SEG U-Net scored under the LeakBench protocol (external_eval/ext_results.json, aggregated here from per-image rows)
ex = json.load(open('external_eval/ext_results.json')); by = collections.defaultdict(list)
for v in ex.values(): by[v['split']].append(v)
for sp, v in by.items():
    dc = [x['dice'] for x in v if 'dice' in x]
    if dc: add('EXT', 'Third-party Kvasir-SEG U-Net (unet.h5) under LeakBench protocol', 'third-party U-Net (unet.h5)', 'Kvasir-SEG (authors)', None, None, sp, len(v), 'mDice', float(np.mean(dc)), 'external_eval/ext_results.json', 'per-image json aggregated', 'partial subsample for ColonDB (200/380)')
    add('EXT', 'Third-party Kvasir-SEG U-Net (unet.h5) under LeakBench protocol', 'third-party U-Net (unet.h5)', 'Kvasir-SEG (authors)', None, None, sp, len(v), 'FA_rate(fg>0.1% frame)' if not dc else 'detect_rate(fg>0.1% frame)', float(np.mean([x['fg'] > 0.001 for x in v])), 'external_eval/ext_results.json', 'per-image json aggregated', 'partial subsample (n shown)')

T = pd.DataFrame(rows)
T['source_folder'] = T.source_file.map(lambda p: p.rsplit('\\', 1)[0])
T['contamination_flag'] = ''
T.loc[T.eval_dataset == 'CVC-ClinicDB (test)', 'contamination_flag'] = 'CONTAMINATED: all 62 test frames come from video sequences present in training (split_v2_report.json, re-read 4 Oct 2026); in-sequence, not unseen-data'
T.loc[T.eval_dataset == 'CVC-ClinicDB 5-fold held-out fold', 'contamination_flag'] = 'E3 CV: video-grouped folds are clean; random folds leak by design (that is the experiment)'
os.makedirs('analysis', exist_ok=True)
T.to_csv('analysis/leakbench_results_tidy.csv', index=False, encoding='utf-8-sig')
print('tidy rows', len(T), '| experiments', T.groupby('experiment').size().to_dict())

# ---- dataset -> results map
FD = os.path.expanduser('~/mnt/chakramodelpro/fixed_polyp_dataset_v1/supervised')
cnt = lambda p: len(os.listdir(p))
disk = {
 'Train': ('training', cnt(FD + '/train/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\train', 1232),
 'Val': ('model selection', cnt(FD + '/val/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\val', 218),
 'Kvasir (test)': ('polyp test', cnt(FD + '/test/kvasir/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\kvasir', 100),
 'CVC-ClinicDB (test)': ('polyp test', cnt(FD + '/test/clinicdb/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\clinicdb', 62),
 'CVC-ColonDB (test)': ('polyp test', cnt(FD + '/test/colondb/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\colondb', 380),
 'ETIS (test)': ('polyp test', cnt(FD + '/test/etis/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\etis', 196),
 'CVC-300 (test)': ('polyp test', cnt(FD + '/test/cvc300/images'), r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\cvc300', 60),
 'PolypGen negatives (4,275)': ('polyp-free eval', cnt(os.path.expanduser('~/mnt/chakramodelpro/negatives_polypgen_v1/images')), r'M:\chakramodelpro\negatives_polypgen_v1\images', 4275),
 'HyperKvasir negatives (2,947)': ('polyp-free eval', None, r'M:\chakramodelpro\negatives_hyperkvasir_v1\images', 2947),
}
M = []
head = {'polyp test': 'mDice', 'polyp-free eval': 'FA_rate(fg>0.1% frame)'}
for ds, (role, n, path, exp_n) in disk.items():
    s = T[(T.eval_dataset == ds) & (T.experiment != 'TP')]
    r = dict(dataset=ds, role=role, expected_images=exp_n, on_disk_images=n if n is not None else '(see note)', disk_path=path,
             experiments_scored=','.join(sorted(s.experiment.unique())) if len(s) else '', n_result_rows=len(s))
    if role in head:
        hm = s[(s.metric == head[role]) & (s.experiment == 'E1')]
        r['headline_metric'] = head[role]
        r['E1_mean_by_model(3 seeds)'] = '; '.join(f'{m}={v:.4f}' for m, v in hm.groupby('model').value.mean().items())
        r['source_files_E1'] = ' | '.join(sorted(hm.source_file.unique()))
        r['source_folders_all'] = ' | '.join(sorted(s.source_folder.unique()))
    elif ds == 'Val':
        hm = T[(T.metric == 'best_val_mDice') & (T.experiment.isin(['E1', 'E2']))]
        r['headline_metric'] = 'best_val_mDice'
        r['experiments_scored'] = ','.join(sorted(hm.experiment.unique())); r['n_result_rows'] = len(hm)
        r['source_files_E1'] = 'E1 val=222 frames (split v2), E2 val=218 frames (v1 random split); one best_val_mDice per run in each results.json'
        r['E1_mean_by_model(3 seeds)'] = '; '.join(f'{e}:{m}={v:.4f}' for (e, m), v in hm.groupby(['experiment', 'model']).value.mean().items())
        r['source_folders_all'] = ' | '.join(sorted(hm.source_folder.unique()))
    else:
        r['headline_metric'] = 'n/a (training data)'
        r['source_folders_all'] = r'training manifests: ' + win('manifests/v2.csv') + ' | ' + win('manifests/std.csv')
    if ds.startswith('HyperKvasir'): r['on_disk_images'] = '4,176 on disk; eval pool = 2,947 frames (manifests/r2_hk_only.csv); E4 manifest lists 3,868 HK frames'
    M.append(r)
# mapped datasets that are not in the LeakBench v1 table
for ds, g in sorted(T[(T.dataset_group.isin(['external polyp', 'polyp-free', 'polyp CV'])) & ~T.eval_dataset.isin(disk.keys())].groupby(['eval_dataset', 'dataset_group']).size().index):
    s = T[(T.eval_dataset == ds)]
    M.append(dict(dataset=ds, role=g, expected_images='', on_disk_images='', disk_path='(see manifests/*.csv; images in the Kaggle datasets)', experiments_scored=','.join(sorted(s.experiment.unique())), n_result_rows=len(s),
                  headline_metric='mDice' if g != 'polyp-free' else 'FA_rate(fg>0.1% frame)', source_folders_all=' | '.join(sorted(s.source_folder.unique()))))
_M = pd.DataFrame(M); _M['flag'] = ''
_M.loc[_M.dataset.str.contains('ClinicDB', na=False) & _M.dataset.str.contains('test', case=False, na=False), 'flag'] = 'CONTAMINATED: all 62 test frames come from video sequences present in training (split_v2_report.json, re-read 4 Oct 2026); in-sequence, not unseen-data'
_M.to_csv('analysis/leakbench_dataset_result_map.csv', index=False, encoding='utf-8-sig')
print('map rows', len(M))
