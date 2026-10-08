"""Plots every combination tried, straight from analysis/leakbench_results_tidy.csv (+ r6/r6_analysis.json for the R6 'hkneg' arm).
Run on the device:  python3 analysis/make_plots.py   -> analysis/plots/*.png"""
import os, json, re, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
H = os.path.expanduser('~/mnt/chakramodelpro/leakbench'); os.chdir(H)
OUT = 'analysis/plots'; os.makedirs(OUT, exist_ok=True)
T = pd.read_csv('analysis/leakbench_results_tidy.csv')
INK, INK2, GRID, BG = '#0b0b0b', '#52514e', '#e6e5e1', '#fcfcfb'
SER = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7']      # categorical slots 1-6 (fixed order)
MODELS = ['unet_r34', 'segformer_b2', 'fpn_pvtv2b2', 'xattn']; MC = dict(zip(MODELS, SER))
MLAB = {'unet_r34': 'U-Net R34 (CNN)', 'segformer_b2': 'SegFormer-B2', 'fpn_pvtv2b2': 'FPN PVTv2-B2', 'xattn': 'ChakraXAttn-UNet'}
TESTS = ['Kvasir (test)', 'CVC-ClinicDB (test)', 'CVC-ColonDB (test)', 'ETIS (test)', 'CVC-300 (test)']
PG, HK = 'PolypGen negatives (4,275)', 'HyperKvasir negatives (2,947)'
FA = 'FA_rate(fg>0.1% frame)'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.facecolor': BG, 'figure.facecolor': BG, 'savefig.facecolor': BG, 'axes.spines.top': False, 'axes.spines.right': False})
def sel(exp, metric, ds=None, **kw):
    d = T[(T.experiment == exp) & (T.metric == metric)]
    if ds is not None: d = d[d.eval_dataset.isin([ds] if isinstance(ds, str) else ds)]
    for k, v in kw.items(): d = d[d[k] == v]
    return d
CLEAN_FIGS = ('F03', 'F05', 'F08')   # negatives-only or CV figures: not affected by the ClinicDB test contamination
def save(fig, name, src):
    if not name.startswith(CLEAN_FIGS):
        fig.text(0.01, 0.03, 'Note (4 Oct 2026): CVC-ClinicDB (test) is contaminated - all 62 frames come from sequences in the training split. Treat it as in-sequence, not unseen-data performance.', fontsize=6.5, color='#b3261e', ha='left', va='bottom')
    fig.text(0.01, 0.005, 'Source: ' + src, fontsize=6.5, color=INK2, ha='left', va='bottom')
    fig.savefig(f'{OUT}/{name}.png', dpi=150, bbox_inches='tight'); plt.close(fig); print('saved', name)
def title(ax, t, sub=None):
    ax.set_title(t, loc='left', fontsize=10.5, color=INK, fontweight='bold', pad=14 if sub else 6)
    if sub: ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8, color=INK2)
def style(ax, grid='y'):
    ax.grid(axis=grid, color=GRID, lw=0.8); ax.set_axisbelow(True)
def ramp(hex_):
    return LinearSegmentedColormap.from_list('r', ['#f5f8fd', hex_, '#0b2a52' if hex_ == '#2a78d6' else '#6b2410'])
def heat(ax, M, rows, cols, cmap, vmin, vmax, fmt='{:.2f}', xl=None):
    im = ax.imshow(M, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=35, ha='right'); ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isfinite(v): ax.text(j, i, fmt.format(v), ha='center', va='center', fontsize=7, color='white' if (v - vmin) / (vmax - vmin + 1e-9) > 0.55 else INK)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0); return im
def grouped(ax, df, cats, key, val='value', hue='model', hues=MODELS, labels=MLAB, colors=MC, dots=True, lab=True, w=0.8, fmt='{:.2f}'):
    n = len(hues); bw = w / n
    for i, h in enumerate(hues):
        for j, c in enumerate(cats):
            v = df[(df[hue] == h) & (df[key] == c)][val].values
            if len(v) == 0: continue
            x = j - w / 2 + bw * (i + .5)
            ax.bar(x, v.mean(), bw * 0.86, color=colors[h], label=labels[h] if j == 0 else None, zorder=2)
            if dots: ax.scatter([x] * len(v), v, s=7, color=INK, zorder=3, lw=0)
            if lab: ax.text(x, v.max() + 0.01 * (ax.get_ylim()[1] or 1), fmt.format(v.mean()), ha='center', va='bottom', fontsize=6, color=INK2, rotation=90)
    ax.set_xticks(range(len(cats))); ax.set_xticklabels(cats)

# F01 / F02: E1 per dataset
for name, met, ttl in [('F01_E1_mDice_by_dataset', 'mDice', 'E1: mean Dice per test dataset'), ('F02_E1_small_polyp_mDice_by_dataset', 'mDice_small_polyps(<5% frame)', 'E1: Dice on small polyps (<5% of frame) per test dataset')]:
    fig, ax = plt.subplots(figsize=(10, 4.2)); ax.set_ylim(0, 1.12); d = sel('E1', met, TESTS)
    grouped(ax, d, TESTS, 'eval_dataset'); style(ax); ax.set_ylabel(met)
    title(ax, ttl, '4 models x 3 seeds, group-aware split v2, 0% negatives. Bars = seed mean, dots = seeds.'); ax.legend(frameon=False, ncol=4, loc='upper center', bbox_to_anchor=(0.5, -0.1), fontsize=8)
    save(fig, name, r'M:\chakramodelpro\leakbench\runs\v2__*\results.json')
# F03: E1 false alarms
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for ax, ds, t in zip(axs, [PG, HK], ['PolypGen (4,275 polyp-free frames)', 'HyperKvasir (2,947 polyp-free frames)']):
    ax.set_ylim(0, 1.15); d = sel('E1', FA, ds); grouped(ax, d, [ds], 'eval_dataset', fmt='{:.2f}'); ax.set_xticklabels([t]); style(ax)
axs[0].set_ylabel('False-alarm rate (fg > 0.1% of frame)'); axs[0].legend(frameon=False, fontsize=8, ncol=4, loc='upper left', bbox_to_anchor=(0, -0.1))
fig.suptitle('E1: SegFormer and FPN-PVT flag ~83-84% of polyp-free frames, XAttn 56-61%, the ResNet U-Net 22-39%', x=0.01, ha='left', fontsize=10.5, fontweight='bold', color=INK)
save(fig, 'F03_E1_false_alarm_rate', r'M:\chakramodelpro\leakbench\runs\v2__*\results.json + r2\ev_e1_hk\*.json')

# F04: E2 vs E1 validation inflation
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for ax, mo in zip(axs, ['unet_r34', 'segformer_b2']):
    vals = {}
    for exp, lab in [('E2', 'v1 random split'), ('E1', 'v2 group-aware split')]:
        v = sel(exp, 'best_val_mDice', model=mo).groupby('seed').value.mean()
        t5 = sel(exp, 'mDice', TESTS, model=mo).groupby('seed').value.mean()
        vals[lab] = (v, t5)
    for k, (lab, (v, t5)) in enumerate(vals.items()):
        for off, arr, col, nm in [(-.19, v, SER[0], 'validation Dice'), (.19, t5, SER[1], 'mean Dice, 5 test sets')]:
            ax.bar(k + off, arr.mean(), .34, color=col, label=nm if k == 0 else None, zorder=2); ax.scatter([k + off] * len(arr), arr, s=8, color=INK, zorder=3, lw=0)
            ax.text(k + off, arr.mean() + .008, f'{arr.mean():.3f}', ha='center', fontsize=7.5, color=INK2)
        gaps = getattr(ax, '_gaps', []); gaps.append(v.mean() - t5.mean()); ax._gaps = gaps
    ax.set_xticks([0, 1]); ax.set_xticklabels([f'{l}\nval - test = {g:.3f}' for l, g in zip(vals, ax._gaps)]); ax.set_ylim(0.45, 1.0); style(ax); ax.set_title(MLAB[mo], loc='left', fontsize=9, color=INK)
axs[0].legend(frameon=False, fontsize=8, loc='upper right'); axs[0].set_ylabel('Dice')
fig.suptitle('E2: validation Dice overstates test Dice under both splits; the random split reads higher on validation', x=0.01, ha='left', fontsize=10.5, fontweight='bold', color=INK)
save(fig, 'F04_E2_validation_vs_test', r'M:\chakramodelpro\leakbench\r2\runs_e2\*\results.json and runs\v2__*\results.json')

# F05: E3 grouped vs random CV
d = sel('E3', 'mDice', 'CVC-ClinicDB 5-fold held-out fold').copy(); d['mode'] = d.note.str.extract(r'cv_mode=(\w+)')[0]; d['fold'] = d.note.str.extract(r'fold=(\d)')[0]
fig, ax = plt.subplots(figsize=(7.5, 4)); ax.set_ylim(0.6, 1.04)
for j, mo in enumerate(['unet_r34', 'segformer_b2']):
    for i, (mode, col) in enumerate([('grouped', SER[0]), ('random', SER[1])]):
        s = d[(d.model == mo) & (d['mode'] == mode)]; fm = s.groupby('fold').value.mean(); x = j + (i - .5) * .36
        ax.bar(x, s.value.mean(), .32, color=col, label=f'{mode} folds' if j == 0 else None, zorder=2); ax.scatter([x] * len(fm), fm.values, s=10, color=INK, zorder=3, lw=0)
        ax.text(x, s.value.mean() + .006, f'{s.value.mean():.3f}', ha='center', fontsize=8, color=INK2)
ax.set_xticks([0, 1]); ax.set_xticklabels([MLAB['unet_r34'], MLAB['segformer_b2']]); style(ax); ax.set_ylabel('Dice on held-out fold'); ax.legend(frameon=False, loc='upper center', ncol=2)
title(ax, 'E3: random frame-level folds inflate ClinicDB Dice', 'Mean of 5 folds x 3 seeds; dots = fold means. Pooled frame-level gap in e3_analysis.json: U-Net +0.066, SegFormer +0.046.')
save(fig, 'F05_E3_clinicdb_grouped_vs_random', r'M:\chakramodelpro\leakbench\runs_e3\leak_f*\results.json')

# F06: negative-ratio curves (E1 = 0%, E4 = 20/50%)
panels = [(t, 'mDice', t) for t in TESTS] + [(PG, FA, 'PolypGen false alarms'), (HK, FA, 'HyperKvasir false alarms')]
fig, axs = plt.subplots(2, 4, figsize=(13, 6.2)); axs = axs.ravel()
for ax, (ds, met, ttl) in zip(axs, panels):
    d = pd.concat([sel('E1', met, ds), sel('E4', met, ds)])
    for mo in MODELS:
        g = d[d.model == mo].groupby('neg_pct_in_training').value; m, s = g.mean(), g.std(ddof=1)
        ax.errorbar(m.index, m.values, yerr=s.values, color=MC[mo], marker='o', ms=4, lw=1.8, capsize=2, label=MLAB[mo])
    ax.set_xticks([0, 20, 50]); ax.set_xlabel('% negatives in training', fontsize=8); style(ax); ax.set_title(ttl, loc='left', fontsize=9, color=INK)
axs[-1].axis('off'); h, l = axs[0].get_legend_handles_labels(); axs[-1].legend(h, l, frameon=False, loc='center', fontsize=9)
fig.suptitle('E4: polyp-free frames in training cut false alarms (HyperKvasir 0.83 -> 0.00 for FPN-PVT); the Dice cost shows mainly on ETIS at 50%', x=0.01, ha='left', fontsize=11, fontweight='bold', color=INK)
fig.text(0.01, 0.93, 'Mean over 3 seeds, whiskers = 1 sd. Y-axes differ per panel.', fontsize=8, color=INK2)
fig.tight_layout(rect=(0, 0.02, 1, 0.95)); save(fig, 'F06_E4_negative_ratio_curves', r'M:\chakramodelpro\leakbench\runs\v2__* + r2\ev_e1_hk + r2\ev_e4')

# F07: S2 external heatmaps
ext = ['PICCOLO (all)', 'PolypGen centre C1', 'PolypGen centre C2', 'PolypGen centre C3', 'PolypGen centre C4', 'PolypGen centre C5', 'PolypGen centre C6', 'PolypDB WLI', 'PolypDB NBI', 'PolypDB BLI', 'PolypDB FICE', 'PolypDB LCI']
fig, axs = plt.subplots(1, 3, figsize=(15, 3.6), sharey=True)
for ax, pct in zip(axs, [0, 20, 50]):
    d = sel('S2', 'mDice', ext, neg_pct_in_training=pct); M = np.array([[d[(d.model == mo) & (d.eval_dataset == c)].value.mean() for c in ext] for mo in MODELS])
    im = heat(ax, M, [MLAB[m] for m in MODELS], ext, ramp('#2a78d6'), 0.2, 0.95); ax.set_title(f'trained with {pct}% negatives', loc='left', fontsize=9, color=INK)
fig.suptitle('S2: external-domain Dice; PolypGen C4 and PolypDB NBI/BLI/FICE fall most as negatives in training increase', x=0.01, ha='left', fontsize=10.5, fontweight='bold', color=INK)
fig.tight_layout(rect=(0, 0.03, 1, 0.9)); save(fig, 'F07_S2_external_domain_mDice', r'M:\chakramodelpro\leakbench\r2\ev_s2\*.json')
# F08: S2 external false alarms
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
for ax, ds in zip(axs, ['PICCOLO negatives', 'PolypGen single-frame negatives']):
    d = sel('S2', FA, ds).copy(); d['cfg'] = d.neg_pct_in_training.map(lambda p: f'{int(p)}% neg')
    ax.set_ylim(0, 1.15); grouped(ax, d, ['0% neg', '20% neg', '50% neg'], 'cfg'); ax.set_title(ds, loc='left', fontsize=9, color=INK); style(ax)
axs[0].set_ylabel('False-alarm rate'); axs[0].legend(frameon=False, fontsize=8, loc='upper right')
fig.suptitle('S2: false alarms on unseen-centre polyp-free frames fall with negatives, but stay high for transformer models', x=0.01, ha='left', fontsize=10.5, fontweight='bold', color=INK)
save(fig, 'F08_S2_external_false_alarms', r'M:\chakramodelpro\leakbench\r2\ev_s2\*.json')

# F09: R5 encoder x decoder grids
R5 = T[T.experiment == 'R5'].copy(); R5['dec'] = R5.model.str.split('_').str[0]; R5['enc'] = R5.model.str.split('_', n=1).str[1]
ENC, DEC = ['r34', 'mit_b2', 'pvtv2b2'], ['unet', 'fpn', 'seg']
def grid(met, ds):
    d = R5[(R5.metric == met) & (R5.eval_dataset.isin(ds if isinstance(ds, list) else [ds]))]
    per = d.groupby(['dec', 'enc', 'seed']).value.mean().groupby(['dec', 'enc']).mean()
    return np.array([[per.get((dd, e), np.nan) for dd in DEC] for e in ENC])
fig, axs = plt.subplots(1, 4, figsize=(14, 3.2))
for ax, (met, ds, ttl, col, lo, hi) in zip(axs, [('mDice', TESTS, 'Mean Dice, 5 tests', '#2a78d6', .78, .87), ('mDice', 'ETIS (test)', 'ETIS Dice', '#2a78d6', .6, .82),
                                                   (FA, PG, 'PolypGen false-alarm rate', '#eb6834', 0, 1), (FA, HK, 'HyperKvasir false-alarm rate', '#eb6834', 0, 1)]):
    heat(ax, grid(met, ds), ENC, [f'{d} decoder' for d in DEC], ramp(col), lo, hi, '{:.3f}' if met == 'mDice' else '{:.2f}'); ax.set_title(ttl, loc='left', fontsize=9, color=INK)
fig.suptitle('R5: false alarms follow the ENCODER (PolypGen spread 0.58 across encoders vs 0.05 across decoders), not the decoder', x=0.01, ha='left', fontsize=10.5, fontweight='bold', color=INK)
fig.tight_layout(rect=(0, 0.03, 1, 0.88)); save(fig, 'F09_R5_encoder_vs_decoder', r'M:\chakramodelpro\leakbench\r5\runs_r5\*\results.json + runs\v2__*\results.json (corner cells)')

# F10: R6 negative diversity (analysis JSON includes the hkneg/E4 arm)
r6 = json.load(open('r6/r6_analysis.json')); arms = ['hkneg (E4)', 'pgneg', 'mixneg']; AC = dict(zip(arms, SER[:3]))
fig, axs = plt.subplots(1, 4, figsize=(14, 3.8))
for ax, (key, ttl) in zip(axs, [('PG_held', 'PolypGen held-out (2,404)'), ('HK', 'HyperKvasir (2,947)'), ('third', 'Third source (168)'), ('dice5', 'Mean Dice, 5 tests')]):
    for j, mo in enumerate(['unet_r34', 'xattn']):
        for i, a in enumerate(arms):
            m, s = r6[mo][a].get(key, [np.nan, np.nan]) if key in r6[mo][a] else (np.nan, np.nan)
            if not np.isfinite(m): continue
            x = j + (i - 1) * .27; ax.bar(x, m, .25, color=AC[a], yerr=s, capsize=2, label=a if j == 0 else None, zorder=2); ax.text(x, m + .01, f'{m:.2f}', ha='center', fontsize=7, color=INK2)
    ax.set_xticks([0, 1]); ax.set_xticklabels(['U-Net R34', 'XAttn-UNet']); ax.set_title(ttl, loc='left', fontsize=9, color=INK); style(ax)
axs[0].legend(frameon=False, fontsize=8, title='negatives from', title_fontsize=8); axs[0].set_ylabel('false-alarm rate (Dice for last panel)')
fig.suptitle('R6: with the same 20% budget, mixed negatives keep false alarms low on both centres; single-centre arms fail on the other centre', x=0.01, ha='left', fontsize=10, fontweight='bold', color=INK)
fig.text(0.01, 0.90, 'HK-only arm (E4) has no third-source or Dice bar here: its Dice is stored as detection rate in r6_analysis.json and is not comparable.', fontsize=7.5, color=INK2)
fig.tight_layout(rect=(0, 0.03, 1, 0.88)); save(fig, 'F10_R6_negative_diversity', r'M:\chakramodelpro\leakbench\r6\r6_analysis.json (from r6\*\results.json + r3\ops)')

# F11: third-party pretrained models
tp = T[(T.experiment == 'TP') & (T.metric == 'mDice')].copy()
tp['lab'] = tp.model + '  |  ' + tp.eval_dataset + '  [' + tp.source_file.str.split('\\').str[-1].str.replace(r'\.(ipynb|xlsx|docx)$', '', regex=True) + ']'; tp = tp.sort_values('value').reset_index(drop=True)
fig, ax = plt.subplots(figsize=(11, 5.4)); bad = tp.note.str.contains('FAILED|identical|INVALID|same 612', na=False) | tp.eval_dataset.str.contains('INVALID|FAILED|TIF')
cols = [('#9b9a96' if b else SER[0]) for b in bad]; ax.barh(range(len(tp)), tp.value, color=cols, height=.7, zorder=2)
ax.set_yticks(range(len(tp))); ax.set_yticklabels(tp.lab, fontsize=7.5)
for y, (v, n) in enumerate(zip(tp.value, tp.eval_n)): ax.text(v + .008, y, f'{v:.3f}  (n={int(n)})', va='center', fontsize=7.5, color=INK2)
ax.set_xlim(0, 1.12); style(ax, 'x'); ax.set_xlabel('mean Dice')
title(ax, 'Third-party pretrained models: reported Dice by dataset (grey = invalid or duplicate rows)', 'Kvasir-SEG / ClinicDB full-set rows include images these models train on; only PraNet-19 ColonDB, ETIS, CVC-300 and ClinicDB-62 are LeakBench-comparable.')
save(fig, 'F11_third_party_pretrained_models', r'M:\chakramodelpro\leakbench\_wcmp\thambi_req\* and external_eval\models\*')

# F12: master heatmap of every trained / evaluated combination
def cfg_rows():
    r = []
    for mo in MODELS: r.append(('E1 0% neg', mo, 'E1', dict(model=mo)))
    for mo in ['unet_r34', 'segformer_b2']: r.append(('E2 v1 random split', mo, 'E2', dict(model=mo)))
    for p in (20, 50):
        for mo in MODELS: r.append((f'E4 {p}% neg', mo, 'E4', dict(model=mo, neg_pct_in_training=p)))
    for cell in sorted(R5.model.unique()):
        if cell not in ('unet_r34', 'seg_mit_b2', 'fpn_pvtv2b2'): r.append(('R5 ablation', cell, 'R5', dict(model=cell)))
    for arm in ('pgneg', 'mixneg'):
        for mo in ('unet_r34', 'xattn'): r.append((f'R6 {arm} 20%', mo, 'R6', dict(model=mo, note=f'arm={arm}')))
    return r
CR = cfg_rows(); rl = [f'{a} | {m}' for a, m, e, k in CR]
def val(e, kw, met, ds):
    d = T[(T.experiment == e) & (T.metric == met) & (T.eval_dataset == ds)]
    for k, v in kw.items(): d = d[d[k] == v]
    if e == 'E4' and ds in (HK,) : pass
    return d.value.mean() if len(d) else np.nan
MD = np.array([[val(e, kw, 'mDice', t) for t in TESTS] for a, m, e, kw in CR])
def fa_val(e, kw, ds):
    if e in ('E2',) and ds == HK: return np.nan
    return val(e, kw, FA, ds)
# E1 HK rows were scored under experiment 'E1' too; E1 FA for HK comes from there
FAM = np.array([[fa_val(e, kw, PG), fa_val(e, kw, HK)] for a, m, e, kw in CR])
fig, axs = plt.subplots(1, 2, figsize=(14, 0.3 * len(CR) + 2.4), gridspec_kw={'width_ratios': [5, 2]}, sharey=True)
heat(axs[0], MD, rl, [t.replace(' (test)', '') for t in TESTS], ramp('#2a78d6'), .5, .95, '{:.3f}'); axs[0].set_title('Mean Dice per test dataset (seed mean)', loc='left', fontsize=9, color=INK)
heat(axs[1], FAM, rl, ['PolypGen FA', 'HyperKvasir FA'], ramp('#eb6834'), 0, 1, '{:.2f}'); axs[1].set_title('False-alarm rate on polyp-free frames', loc='left', fontsize=9, color=INK)
fig.suptitle('All trained combinations: Dice (left) and false alarms (right). Blank = not scored in that experiment.', x=0.01, ha='left', fontsize=11, fontweight='bold', color=INK)
fig.tight_layout(rect=(0, 0.02, 1, 0.97)); save(fig, 'F12_all_combinations_heatmap', r'M:\chakramodelpro\leakbench\analysis\leakbench_results_tidy.csv')

# F13: accuracy vs false alarms trade-off, every trained config
fig, ax = plt.subplots(figsize=(8.5, 5.4))
pts = []
for a, m, e, kw in CR:
    x, y = val(e, kw, 'mDice', TESTS[0]), None
    d5 = np.nanmean([val(e, kw, 'mDice', t) for t in TESTS]); fa_ = val(e, kw, FA, PG)
    if np.isfinite(d5) and np.isfinite(fa_): pts.append((a, m, d5, fa_))
MK = {'E1': 'o', 'E4 20': 's', 'E4 50': '^', 'E2': 'x', 'R5': 'D', 'R6': 'P'}
for a, m, d5, fa_ in pts:
    k = 'E4 20' if a.startswith('E4 20') else 'E4 50' if a.startswith('E4 50') else a.split()[0]; col = MC.get(m, '#9b9a96')
    ax.scatter(fa_, d5, s=55, marker=MK.get(k, 'o'), color=col, **({} if k == 'E2' else dict(edgecolor=BG)), lw=1.4 if k == 'E2' else 1, zorder=3)
    if a.startswith('R5'):
        i = sum(1 for q in ax.texts); off = [(4, 4), (4, -9), (-52, 4), (-52, -9)][i % 4]
        ax.annotate(m.replace('_', ' '), (fa_, d5), fontsize=6, color=INK2, xytext=off, textcoords='offset points')
ax.set_xlabel('PolypGen false-alarm rate (lower is better)'); ax.set_ylabel('Mean Dice over 5 test sets (higher is better)'); style(ax, 'both')
from matplotlib.lines import Line2D
h = [Line2D([], [], marker='o', ls='', color=MC[m], label=MLAB[m]) for m in MODELS] + [Line2D([], [], marker='o', ls='', color='#9b9a96', label='R5/R6 other cells')]
h += [Line2D([], [], marker=MK[k], ls='', color=INK2, label=l) for k, l in [('E1', 'E1 / 0% neg'), ('E4 20', 'E4 20% neg'), ('E4 50', 'E4b 50% neg'), ('E2', 'E2 random split'), ('R5', 'R5 ablation'), ('R6', 'R6 diversity')]]
ax.legend(handles=h, frameon=False, fontsize=7.5, ncol=2, loc='lower left')
title(ax, 'Accuracy vs false alarms across every trained configuration', 'Highest Dice (0.85) comes with PolypGen false alarms >= 0.84; lowest false alarms (0.17, U-Net 50% neg) come with Dice 0.785.')
save(fig, 'F13_tradeoff_all_configs', r'M:\chakramodelpro\leakbench\analysis\leakbench_results_tidy.csv')
print('DONE')
