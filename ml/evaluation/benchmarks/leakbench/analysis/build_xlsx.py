"""Builds LeakBench_v1_metrics.xlsx from the result files under M:\chakramodelpro\leakbench.
Run from the device shell:  python3 analysis/build_xlsx.py   (reads ~/mnt/chakramodelpro/...)"""
import json, glob, os, collections, numpy as np, pandas as pd
H = os.path.expanduser('~/mnt/chakramodelpro/leakbench'); os.chdir(H)
WIN = r'M:\chakramodelpro\leakbench'
def win(rel): return WIN + '\\' + rel.replace('/', '\\')
T = ['test_kvasir','test_clinicdb','test_colondb','test_etis','test_cvc300']
S = {}

# ---- Notebook index
nb = [
 (1,'pranet-tf.ipynb','_wcmp/thambi_req/pranet tf/author & og/pranet-tf.ipynb','Third-party eval: PraNet (TensorFlow re-impl., ResNet50 SavedModel)','Kvasir-SEG (1000)','Kvasir-SEG n=1000: mDice 0.9138, mIoU 0.8615, MAE 0.0305 (18.8 s). LDPolypVideo cell failed (ModuleNotFoundError).','_wcmp/thambi_req/pranet tf/author & og/kvasir_per_image_metrics.xlsx','Scored on all 1000 Kvasir-SEG images, not the 100-image LeakBench test split. Not comparable to LeakBench.'),
 (2,'pranetv2.ipynb','_wcmp/thambi_req/pranet v2/author/pranetv2.ipynb','Third-party eval: PraNet-V2 (binary_seg, Res2Net50)','Kvasir-SEG (1000), CVC-ClinicDB PNG (612)','Kvasir-SEG mDice 0.0086, mIoU 0.0045; ClinicDB mDice 0.0049, mIoU 0.0025.','_wcmp/thambi_req/pranet v2/og/per_image_metrics.xlsx','FAILED RUN: near-zero Dice means a pipeline fault (2 unexpected keys at weight load; cause not confirmed), not model quality. Do not cite.'),
 (3,'pranetcod.ipynb','_wcmp/thambi_req/pranet-19/author/pranetcod.ipynb','Third-party eval: PraNet-19 (official PyTorch, PraNet-19.pth)','Kvasir 100, ClinicDB 62, CVC-300 60, ColonDB 380, ETIS 196 (= 798, identical to LeakBench test)','Notebook saves masks only. Metrics are in the og .docx (run on Kvasir=1000): Kvasir 0.9711, ClinicDB 0.9012, CVC-300 0.8864, ColonDB 0.7102, ETIS 0.6132 mDice.','_wcmp/thambi_req/pranet-19/og/pranetcod.docx','Only notebook whose test sets match LeakBench exactly, but the docx Kvasir row used 1000 images (includes images PraNet trains on).'),
 (4,'sepnet (1).ipynb','_wcmp/thambi_req/sepnet/author/sepnet (1).ipynb','Third-party eval: SEPNet (PVTv2-B2, TCSVT 2024)','Kvasir-SEG (1000); ClinicDB not found','Kvasir-SEG n=1000: mDice 0.9694, mIoU 0.9427.','_wcmp/thambi_req/sepnet/author/all_images_metrics.xlsx','Full Kvasir-SEG, not held out. 0.97 Dice is far above any LeakBench unseen-domain score.'),
 (5,'sepnet (3).ipynb','_wcmp/thambi_req/sepnet/og/sepnet (3).ipynb','Third-party eval: SEPNet (same weights, ClinicDB added)','Kvasir-SEG 1000; ClinicDB PNG 612; ClinicDB TIF 612','Kvasir 0.9695/0.9430 (mDice/mIoU); ClinicDB PNG 0.9632/0.9302; ClinicDB TIF 0.9387/0.8948; 2,224 files scored.','_wcmp/thambi_req/sepnet/og/all_images_metrics (2).xlsx','PNG and TIF folders are the same 612 frames in two formats, so 2,224 is really 1,612 distinct images.'),
 (6,'chakra_r3_operating_points.ipynb','chakra_r3_operating_points.ipynb','R3: re-score 36 checkpoints (E1 0%, E4 20%, E4b 50% negatives) at thresholds 0.5-0.99 + connected components','LeakBench v2 manifests (5 tests + PolypGen + HyperKvasir negatives)','Code only, no outputs saved in the notebook. Results: r3/r3_analysis.json, r3/cascade_analysis.json, r3/ops/ (36 .ops.json).','r3/','Results live outside the notebook.'),
 (7,'chakra_r4_e3_seeds.ipynb','chakra_r4_e3_seeds.ipynb','R4: E3 seeds 43,44 (40 runs: 5 folds x grouped/random x U-Net/SegFormer)','ClinicDB 612 frames, 5-fold','Code only. Results: runs_e3/ (60 run folders for 3 seeds) + runs_e3/e3_analysis.json.','runs_e3/','Results live outside the notebook.'),
 (8,'chakra_r5_encoder_decoder_ablation.ipynb','chakra_r5_encoder_decoder_ablation.ipynb','R5: 3 encoders x 3 decoders, 18 runs','5 tests + 4,275 PolypGen + 2,947 HyperKvasir negatives','Code only. Results: r5/runs_r5/ (18 runs), r5/r5_analysis.json.','r5/','Results live outside the notebook.'),
 (9,'chakra_r6_negative_diversity.ipynb','chakra_r6_negative_diversity.ipynb','R6: negative-sample diversity (HK-only vs PG-only vs mixed), 12 runs','Held-out PolypGen 2,404 (12 seqs), HyperKvasir 2,947, third source 168','Code only. Results: r6/ (12 run folders), r6/results_table.csv, r6/r6_analysis.json.','r6/','Results live outside the notebook.'),
 (10,'unet_inference.ipynb','external_eval/models/chakraunet/unet_inference.ipynb','Third-party Keras U-Net (unet__1_.h5) inference on a held-out test set','Kvasir / colon test set','No outputs saved in notebook. A third-party Kvasir-SEG U-Net (unet.h5) was scored under LeakBench protocol in external_eval/ext_results.json (see ExtModel_LeakBench sheet).','external_eval/ext_results.json','results.lnk points to C:\\Users\\varsh\\Downloads\\results.zip (not on this drive).'),
 (11,'compnet-testing-24-09-26-9-40.ipynb','external_eval/models/compnet/compnet-testing-24-09-26-9-40.ipynb','CompNet (5.01M params, 512 px) eval with sanity checks','Kvasir-SEG 1000 (debeshjha1)','Dice 0.8631 [0.8538-0.8722], IoU 0.7822, precision 0.8738, recall 0.8804, micro Dice 0.8838; 167.6 ms/img; threshold sweep 0.1-0.9 peaks 0.8634 at 0.6.','external_eval/models/compnet/compnet_arch_and_eval.txt','Weights from gokulrocky/giruba. Kvasir-SEG only; training split not stated in the notebook.'),
 (12,'pranet (2).ipynb','external_eval/models/pranetf/pranet (2).ipynb','PraNet-TF eval (resnet50), Kvasir-SEG and LDPolypVideo','Kvasir-SEG 1000; LDPolypVideo 1000','Kvasir: Dice 0.9191, IoU 0.8700, MAE 0.0294. LDPolypVideo row is IDENTICAL (0.9191/0.8700/0.0294, n=1000).','external_eval/models/pranetf/pranet (2).ipynb','INVALID LDPolypVideo row: identical to Kvasir to 4 decimals, so the same data was scored twice. Also differs from notebook 1 (0.9138) with the same repo.'),
 (13,'saved_model.ipynb','external_eval/models/pranetf/saved_model.ipynb','Unmodified TensorFlow docs tutorial (SavedModel guide)','n/a','No LeakBench content, no results.','','Stock TF tutorial; safe to ignore.'),
 (14,'kaggle_runner.ipynb','kaggle_runner.ipynb','E1/E2/E3 job runner (run_queue.py over jobs.csv, 90 jobs)','LeakBench v1 dataset (chakra-leakbench-v1)','Code only. Results: runs/ (E1, 12 runs + results_table.csv), r2/runs_e2 (E2, 6 runs), runs_e3/ (E3).','runs/','Results live outside the notebook.'),
]
S['Notebook_Index'] = pd.DataFrame([dict(No=a, Notebook=b, Folder_Path=win(os.path.dirname(c)) if os.path.dirname(c) else WIN, Full_Path=win(c), Purpose=d, Data=e, Results_Metrics=f, Results_Location=(win(g) if g else ''), Flags=h) for a,b,c,d,e,f,g,h in nb])

# ---- Dataset counts
FD = os.path.expanduser('~/mnt/chakramodelpro/fixed_polyp_dataset_v1/supervised')
pg = os.path.expanduser('~/mnt/chakramodelpro/negatives_polypgen_v1/images')
def cnt(p): return len(os.listdir(p))
rows = [('Train','1,232',cnt(FD+'/train/images'),cnt(FD+'/train/masks'),r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\train'),
        ('Val','218',cnt(FD+'/val/images'),cnt(FD+'/val/masks'),r'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\val')]
for nm,k,e in [('CVC-ColonDB','colondb','380'),('ETIS','etis','196'),('CVC-ClinicDB','clinicdb','62'),('CVC-300','cvc300','60'),('Kvasir','kvasir','~100 (collapsed)')]:
    rows.append((f'Test: {nm}',e,cnt(f'{FD}/test/{k}/images'),cnt(f'{FD}/test/{k}/masks'),rf'M:\chakramodelpro\fixed_polyp_dataset_v1\supervised\test\{k}'))
df = pd.DataFrame(rows, columns=['Split','Expected','On_disk_images','On_disk_masks','Path'])
tot_test = int(df.loc[df.Split.str.startswith('Test'),'On_disk_images'].sum()); pos = int(df.On_disk_images.sum()); neg = cnt(pg)
share = [round(100*x/pos,2) for x in df.On_disk_images]
df.loc[len(df)] = ['Test total','698+',tot_test,tot_test,r'...\supervised\test']
df.loc[len(df)] = ['Positives total','2,148',pos,pos,'']
df.loc[len(df)] = ['Negatives (PolypGen, eval only)','4,275',neg,'',r'M:\chakramodelpro\negatives_polypgen_v1\images']
df.loc[len(df)] = ['Combined','6,423',pos+neg,'','']
df['Share_of_positives_%'] = share + [round(100*tot_test/pos,2), 100.0, None, None]
S['Dataset_Counts'] = df
print(df.to_string())
print('ratio pos:neg = 1 : %.3f ; pos%% %.2f neg%% %.2f' % (neg/pos, 100*pos/(pos+neg), 100*neg/(pos+neg)))

# ---- E1
r1 = []
for f in sorted(glob.glob('runs/v2__*/results.json')):
    r = json.load(open(f)); row = dict(run=r['tag'], model=r['model'], seed=r['seed'], epochs=r['epochs'], train_n=r['train_n'], val_n=r['val_n'], best_val_mDice=r['best_val_mDice'], params_M=r['params']/1e6, fps_fp16_bs1=r['latency']['fps_bs1_fp16'], peak_vram_MB=r['latency']['peak_vram_mb'], train_min=r['train_minutes'], path=win(os.path.dirname(f)))
    for t in T:
        for k in ('mDice','mIoU','MAE','mDice_small'): row[f'{t}_{k}'] = r['tests'][t][k]
    row['mean5_mDice'] = float(np.mean([r['tests'][t]['mDice'] for t in T]))
    n = r['tests']['neg_polypgen']; row['PG_FA@0.0']=n['false_alarm_rate@0.0']; row['PG_FA@0.1%']=n['false_alarm_rate@0.001']; row['PG_FA@1%']=n['false_alarm_rate@0.01']
    r1.append(row)
d1 = pd.DataFrame(r1); S['E1_per_run'] = d1
num = [c for c in d1.columns if c not in ('run','model','seed','epochs','train_n','val_n','path')]
g = d1.groupby('model')[num]; m = g.mean().add_suffix('_mean'); s_ = g.std(ddof=1).add_suffix('_sd')
S['E1_summary'] = pd.concat([m, s_], axis=1).reset_index()

# ---- E2
d = json.load(open('r2/r2_analysis.json')); rows=[]
for mo in ('unet_r34','segformer_b2'):
    a, b = d[f'E2|{mo}|std'], d[f'E2|{mo}|v2']
    rows.append(dict(model=mo, split='v1 random (std)', val_mDice=a['val'], test5_mDice=a['test5'], val_minus_test=a['val']-a['test5'], clinicdb_test=a['clinic']))
    rows.append(dict(model=mo, split='v2 group-aware', val_mDice=b['val'], test5_mDice=b['test5'], val_minus_test=b['val']-b['test5'], clinicdb_test=b['clinic']))
S['E2_val_inflation'] = pd.DataFrame(rows)

# ---- E3
e3 = json.load(open('runs_e3/e3_analysis.json')); rows=[]
for mo,v in e3.items():
    rows.append(dict(model=mo, n_frames=v['n_frames'], n_video_seq=v['n_seq'], grouped_dice=v['grouped'], random_dice=v['random'], inflation=v['gap'], ci95_lo=v['ci95'][0], ci95_hi=v['ci95'][1], wilcoxon_p_seq=v['p_seq_wilcoxon'], seq_pos=v['seq_pos'], seq_neg=v['seq_neg'], small_n=v['small_n'], inflation_small=v['gap_small'], inflation_large=v['gap_large'], frac_fail_grouped=v['frac_fail_grouped'], frac_fail_random=v['frac_fail_random'], val_grouped=v['val_grouped'], val_random=v['val_random']))
S['E3_clinicdb_leak'] = pd.DataFrame(rows)

# ---- E4 neg-ratio curve
rows=[]
for k,v in d['curve'].items():
    mo,p = k.split('|')
    row = dict(model=mo, neg_pct_in_training=int(p))
    for key in ('test_kvasir','test_clinicdb','test_colondb','test_etis','test_cvc300','mean5','small_all','neg_polypgen@0.1%','neg_polypgen@1%','neg_polypgen_conf99','neg_hyperkvasir@0.1%','neg_hyperkvasir@1%','neg_hyperkvasir_conf99'):
        row[key+'_mean']=v[key][0]; row[key+'_sd']=v[key][1]
    rows.append(row)
S['E4_negative_ratio'] = pd.DataFrame(rows)

# ---- S2
s2 = json.load(open('r2/s2_analysis.json')); rows=[]
for k,v in s2.items():
    mo,p = k.split('|'); row=dict(model=mo, neg_pct=int(p))
    for key,x in v.items(): row[key+'_mean']=x[0]; row[key+'_sd']=x[1]
    rows.append(row)
S['S2_external_transfer'] = pd.DataFrame(rows)

# ---- R3
r3 = json.load(open('r3/r3_analysis.json')); rows=[]
for k,v in r3.items():
    _,mo,p = k.split('|')
    rows.append(dict(model=mo, neg_pct=int(p), raw_in_domain_detect=v['neg'][0], raw_ETIS_detect=v['neg'][1], raw_external_detect=v['neg'][2], raw_PG_false_alarm=v['neg'][3], e1_tuned_in_domain_detect=v['e1'][0], e1_tuned_ETIS_detect=v['e1'][1], e1_tuned_external_detect=v['e1'][2], e1_tuned_PG_false_alarm=v['e1'][3], e1_rules_per_seed=str(v['rules'])))
S['R3_matched'] = pd.DataFrame(rows)
cs = json.load(open('r3/cascade_analysis.json')); rows=[]
for k,v in cs.items():
    seg,gate = k.split('|'); df_=pd.DataFrame(v)
    rows.append(dict(segmenter=seg, gate=gate, in_domain_detect=df_['in'].mean(), in_domain_alone=df_['in_alone'].mean(), ETIS_detect=df_['etis'].mean(), ETIS_alone=df_['etis_alone'].mean(), external_detect=df_['ext'].mean(), external_alone=df_['ext_alone'].mean(), PG_false_alarm=df_['PG'].mean(), PG_alone=df_['PG_alone'].mean(), HK_false_alarm=df_['HK'].mean(), HK_alone=df_['HK_alone'].mean(), gate_rules=str([tuple(r) for r in df_['rule']])))
S['R3_cascade'] = pd.DataFrame(rows)

# ---- R5
r5 = json.load(open('r5/r5_analysis.json')); rows=[]
for k,v in r5.items():
    dec,enc = k.split('_',1); row=dict(cell=k, decoder=dec, encoder=enc)
    for key,x in v.items(): row[key+'_mean']=x[0]; row[key+'_sd']=x[1]
    rows.append(row)
d5 = pd.DataFrame(rows); S['R5_encoder_decoder'] = d5
for key in ('PG_mean','HK_mean','dice5_mean'):
    pv = d5.pivot(index='encoder', columns='decoder', values=key)
    print(key, 'encoder spread %.3f | decoder spread %.3f' % (pv.mean(1).max()-pv.mean(1).min(), pv.mean(0).max()-pv.mean(0).min()))
    print(pv.round(3).to_string())

# ---- R6
r6 = json.load(open('r6/r6_analysis.json')); rows=[]
for mo,arms in r6.items():
    for arm,v in arms.items():
        row=dict(model=mo, arm=arm)
        for key,x in v.items(): row[key+'_mean']=x[0]; row[key+'_sd']=x[1]
        rows.append(row)
S['R6_neg_diversity'] = pd.DataFrame(rows)
S['R6_per_run'] = pd.read_csv('r6/results_table.csv')

# ---- External model under LeakBench protocol
ex = json.load(open('external_eval/ext_results.json')); by=collections.defaultdict(list)
for k,v in ex.items(): by[v['split']].append(v)
rows=[]
for sp,v in by.items():
    dc=[x['dice'] for x in v if 'dice' in x]
    rate=float(np.mean([x['fg']>0.001 for x in v]))
    rows.append(dict(split=sp, n_scored=len(v), mDice=float(np.mean(dc)) if dc else None, rate_fg_gt_0p1pct=rate, meaning=('detection rate' if dc else 'false-alarm rate')))
S['ExtModel_LeakBench'] = pd.DataFrame(rows)

# ---- ChakraGuard
cg = json.load(open('chakraguard/operating_point.json')); rows=[dict(seed=k, **v) for k,v in cg['per_seed'].items()]
rows.append(dict(seed='chosen('+str(cg['chosen_seed'])+')', **cg['rule']))
S['ChakraGuard_operating_pt'] = pd.DataFrame(rows)

# ---- Pretrained-model audit
S['PreTrained_Model_Audit'] = pd.DataFrame([
 dict(model='PraNet-19 (official, PyTorch)', notebook='pranetcod.docx', dataset='Kvasir (1000 in docx run)', n=1000, mDice=0.9711, mIoU=0.9477, MAE=0.0076),
 dict(model='PraNet-19', notebook='pranetcod.docx', dataset='CVC-ClinicDB', n=62, mDice=0.9012, mIoU=0.8533, MAE=0.0095),
 dict(model='PraNet-19', notebook='pranetcod.docx', dataset='CVC-300', n=60, mDice=0.8864, mIoU=0.8137, MAE=0.0080),
 dict(model='PraNet-19', notebook='pranetcod.docx', dataset='CVC-ColonDB', n=380, mDice=0.7102, mIoU=0.6395, MAE=0.0362),
 dict(model='PraNet-19', notebook='pranetcod.docx', dataset='ETIS-LaribPolypDB', n=196, mDice=0.6132, mIoU=0.5490, MAE=0.0164),
 dict(model='PraNet-TF (ResNet50)', notebook='pranet-tf.ipynb', dataset='Kvasir-SEG', n=1000, mDice=0.9138, mIoU=0.8615, MAE=0.0305),
 dict(model='PraNet-TF (ResNet50)', notebook='pranet (2).ipynb', dataset='Kvasir-SEG', n=1000, mDice=0.9191, mIoU=0.8700, MAE=0.0294),
 dict(model='PraNet-TF (ResNet50)', notebook='pranet (2).ipynb', dataset='LDPolypVideo (INVALID, duplicates Kvasir row)', n=1000, mDice=0.9191, mIoU=0.8700, MAE=0.0294),
 dict(model='PraNet-V2', notebook='pranetv2.ipynb', dataset='Kvasir-SEG (FAILED RUN)', n=1000, mDice=0.0086, mIoU=0.0045, MAE=None),
 dict(model='PraNet-V2', notebook='pranetv2.ipynb', dataset='CVC-ClinicDB PNG (FAILED RUN)', n=612, mDice=0.0049, mIoU=0.0025, MAE=None),
 dict(model='SEPNet (PVTv2-B2)', notebook='sepnet (3).ipynb', dataset='Kvasir-SEG', n=1000, mDice=0.9695, mIoU=0.9430, MAE=None),
 dict(model='SEPNet', notebook='sepnet (3).ipynb', dataset='CVC-ClinicDB PNG', n=612, mDice=0.9632, mIoU=0.9302, MAE=None),
 dict(model='SEPNet', notebook='sepnet (3).ipynb', dataset='CVC-ClinicDB TIF (same frames as PNG)', n=612, mDice=0.9387, mIoU=0.8948, MAE=None),
 dict(model='CompNet (5.01M)', notebook='compnet-testing-24-09-26-9-40.ipynb', dataset='Kvasir-SEG', n=1000, mDice=0.8631, mIoU=0.7822, MAE=None),
])

out = os.path.join(H, 'analysis', 'LeakBench_v1_metrics.xlsx')
with pd.ExcelWriter(out, engine='openpyxl') as w:
    for k,v in S.items(): v.to_excel(w, sheet_name=k[:31], index=False)
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
wb = load_workbook(out)
for ws in wb.worksheets:
    for c in ws[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='305496'); c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A2'
    for col in ws.columns:
        L = max(len(str(c.value)) if c.value is not None else 0 for c in col[:60]); ws.column_dimensions[col[0].column_letter].width = min(max(10, L+2), 70)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, float): c.number_format = '0.0000'
            if isinstance(c.value, str) and len(c.value) > 70: c.alignment = Alignment(wrap_text=True, vertical='top')
wb.save(out); print('saved', out, [ws.title for ws in wb.worksheets])
