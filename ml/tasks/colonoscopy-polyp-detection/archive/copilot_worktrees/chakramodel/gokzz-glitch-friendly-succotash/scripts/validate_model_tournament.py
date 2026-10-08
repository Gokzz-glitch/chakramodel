import argparse
from pathlib import Path
import yaml
REQUIRED={'unet_resnet34','pranet','polyp_pvt','segformer_b2','medsam','polyp_sam','chakra_xattn_unet'}
def main():
 p=argparse.ArgumentParser(); p.add_argument('--config',type=Path,default=Path('configs/model_tournament.yaml')); a=p.parse_args(); c=yaml.safe_load(a.config.read_text(encoding='utf-8')); errors=[]
 d=c['data']; pol=d['policy']
 if pol['train_only']!=d['train']: errors.append('train_only must equal train')
 if pol['never_train_on']!='external_test': errors.append('external_test must be excluded from training')
 ids={m['id'] for m in c['models']}; miss=REQUIRED-ids
 if miss: errors.append(f'missing models: {sorted(miss)}')
 metrics=set(c['metrics']['primary']+c['metrics']['secondary'])
 for x in {'dice','iou','parameters','latency_ms','peak_vram_mb'}-metrics: errors.append(f'missing metric: {x}')
 if c['protocol']['checkpoint_selection']!='validation_dice': errors.append('checkpoint selection must use validation Dice')
 if errors:
  print('\n'.join('ERROR: '+x for x in errors)); return 1
 print(f'PASS models={len(ids)} external_sets={len(d["external_test"])} metrics={len(metrics)} seed={c["protocol"]["seed"]}'); return 0
if __name__=='__main__': raise SystemExit(main())
