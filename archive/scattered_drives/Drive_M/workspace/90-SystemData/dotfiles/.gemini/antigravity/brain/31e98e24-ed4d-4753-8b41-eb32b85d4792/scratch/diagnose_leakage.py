import pandas as pd
from pathlib import Path

root = Path(r'M:/chakramodelpro/polyp-detection-research')
train = pd.read_csv(root / 'data/processed/manifests/train_pranet.tsv', sep='\t')
colondb = pd.read_csv(root / 'data/processed/manifests/test_cvc_colondb.tsv', sep='\t')
etis = pd.read_csv(root / 'data/processed/manifests/test_etis_laribpolypdb.tsv', sep='\t')
cvc300 = pd.read_csv(root / 'data/processed/manifests/test_cvc_300.tsv', sep='\t')

train_stems = set(train['image'].apply(lambda x: Path(x).stem))

print("=== TRAIN STEMS SAMPLE ===")
print(sorted(list(train_stems))[:15])

print("\n=== CVC-ColonDB TEST STEMS SAMPLE ===")
colondb_stems = set(colondb['image'].apply(lambda x: Path(x).stem))
print(sorted(list(colondb_stems))[:15])
print(f"Overlap count: {len(train_stems & colondb_stems)}")

print("\n=== ETIS TEST STEMS SAMPLE ===")
etis_stems = set(etis['image'].apply(lambda x: Path(x).stem))
print(sorted(list(etis_stems))[:15])
print(f"Overlap count: {len(train_stems & etis_stems)}")

print("\n=== CVC-300 TEST STEMS SAMPLE ===")
cvc300_stems = set(cvc300['image'].apply(lambda x: Path(x).stem))
print(sorted(list(cvc300_stems))[:15])
print(f"Overlap count: {len(train_stems & cvc300_stems)}")

# Show full paths of overlapping entries
print("\n=== FULL PATHS OF OVERLAPPING ENTRIES (CVC-ColonDB, first 5) ===")
overlap = train_stems & colondb_stems
for stem in sorted(list(overlap))[:5]:
    train_rows = train[train['image'].apply(lambda x: Path(x).stem) == stem]
    test_rows = colondb[colondb['image'].apply(lambda x: Path(x).stem) == stem]
    train_path = train_rows.iloc[0]['image']
    test_path = test_rows.iloc[0]['image']
    print(f"  TRAIN: {train_path}")
    print(f"  TEST:  {test_path}")
    print()
