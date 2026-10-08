"""Aggregate every results.json under a folder (leakbench train.py format and chakraseg_v3 format),
plus progress of unfinished runs from their logs / train_meta.json."""
import json, os, sys, glob, re
import numpy as np, pandas as pd

root = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else '.'
recs, runs = [], []
for rj in sorted(glob.glob(os.path.join(root, '**', 'results.json'), recursive=True)):
    try:
        d = json.load(open(rj))
    except Exception as e:
        print('unreadable', rj, e); continue
    rd = os.path.dirname(rj)
    if 'tests' in d:
        cfg = f"{os.path.splitext(d.get('manifest',''))[0]}|{d.get('model')}"
        runs.append(dict(fmt='leakbench', config=cfg, seed=d.get('seed'), dir=os.path.relpath(rd, root),
                         best_val=d.get('best_val_mDice'), epochs_run=len(d.get('log', [])), epochs=d.get('epochs'),
                         minutes=d.get('train_minutes'), eff_batch=d.get('effective_batch'), bs=d.get('bs'), accum=d.get('accum'),
                         llrd=d.get('llrd'), drop_path=d.get('drop_path'), clip=d.get('clip'), warmup=d.get('warmup_frac'),
                         size=d.get('size'), params_M=(d.get('params') or 0) / 1e6, n_gpu=d.get('n_gpu'),
                         gpus=','.join(d.get('gpu_names', [])), amp=d.get('amp_dtype'),
                         fps=(d.get('latency') or {}).get('fps_bs1_fp16'), eval_errors=json.dumps(d.get('eval_errors', {}))[:200],
                         train_n=d.get('train_n'), val_n=d.get('val_n')))
        for split, s in d['tests'].items():
            recs.append(dict(config=cfg, seed=d.get('seed'), split=split, n=s.get('n'), mDice=s.get('mDice'),
                             mIoU=s.get('mIoU'), mDice_small=s.get('mDice_small'), n_small=s.get('n_small'),
                             fa0=s.get('false_alarm_rate@0.0'), fa001=s.get('false_alarm_rate@0.001'),
                             fa01=s.get('false_alarm_rate@0.01'), mean_fg=s.get('mean_fg_frac')))
    elif 'splits' in d:
        cfgj = json.load(open(os.path.join(rd, 'config.json'))) if os.path.isfile(os.path.join(rd, 'config.json')) else {}
        name = cfgj.get('run_name') or os.path.basename(rd)
        cfg = 'v3|' + re.sub(r'_s\d+$', '', name)
        runs.append(dict(fmt='chakraseg_v3', config=cfg, seed=cfgj.get('seed'), dir=os.path.relpath(rd, root),
                         best_val=d['meta'].get('best_val'), minutes=d['meta'].get('minutes'),
                         params_M=d['meta'].get('params_total', 0) / 1e6, fps=d.get('fps')))
        for split, s in d['splits'].items():
            recs.append(dict(config=cfg, seed=cfgj.get('seed'), split=split, n=s.get('n'), mDice=s.get('gated_mDice'),
                             mIoU=s.get('gated_mIoU'), fa001=s.get('gated_fa_rate'), raw_mDice=s.get('raw_mDice'),
                             raw_fa=s.get('raw_fa_rate')))
R = pd.DataFrame(runs); T = pd.DataFrame(recs)
R.to_csv(os.path.join(out, 'runs_found.csv'), index=False); T.to_csv(os.path.join(out, 'tests_long.csv'), index=False)
print(f'{len(R)} finished runs'); print(R.to_string(max_colwidth=60))
if len(T):
    pos = T[T.split.str.startswith('test_')]
    if len(pos):
        g = pos.groupby(['config', 'split']).agg(mean=('mDice', 'mean'), sd=('mDice', 'std'), seeds=('seed', 'nunique')).reset_index()
        print('\nmDice mean over seeds'); print(g.pivot(index='config', columns='split', values='mean').round(4).to_string())
        print('\nsd over seeds'); print(g.pivot(index='config', columns='split', values='sd').round(4).to_string())
        print('\nseeds'); print(g.pivot(index='config', columns='split', values='seeds').to_string())
    neg = T[T.split.str.startswith('neg_')]
    if len(neg):
        h = neg.groupby(['config', 'split']).agg(fa=('fa001', 'mean'), sd=('fa001', 'std'), seeds=('seed', 'nunique')).reset_index()
        print('\nfalse-alarm rate @0.001 (mean over seeds)'); print(h.pivot(index='config', columns='split', values='fa').round(4).to_string())
# unfinished runs: any folder with train_meta.json or best.pt but no results.json, and any log files
print('\n--- unfinished / other artefacts')
for p in sorted(glob.glob(os.path.join(root, '**', '*'), recursive=True)):
    if os.path.isdir(p) and not os.path.isfile(os.path.join(p, 'results.json')):
        if os.path.isfile(os.path.join(p, 'best.pt')) or os.path.isfile(os.path.join(p, 'train_meta.json')):
            print('no results.json:', os.path.relpath(p, root), os.listdir(p))
