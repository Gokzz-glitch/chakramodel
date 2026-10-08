import json
import re

def test_cross_validation():
    with open('kaggle_results/run_v5/cross_dataset_results_v5.json', 'r') as f:
        v5 = json.load(f)

    with open('paper/main.tex', 'r', encoding='utf-8') as f:
        tex = f.read()

    with open('docs/paper/ChakraModel_Final_Paper.md', 'r', encoding='utf-8') as f:
        md = f.read()

    with open('docs/HONEST_METRICS.md', 'r', encoding='utf-8') as f:
        honest = f.read()

    mapping = {
        'Kvasir-SEG (test split)': {'dice': '0.8131', 'std': '0.1747', 'iou': '0.7141', 'prec': '0.8330', 'rec': '0.8500', 'n': 150},
        'HyperKvasir Segmented': {'dice': '0.8360', 'std': '0.1610', 'iou': '0.7439', 'prec': '0.8398', 'rec': '0.8768', 'n': 1000},
        'CVC-ClinicDB (zero-shot)': {'dice': '0.7561', 'std': '0.2131', 'iou': '0.6470', 'prec': '0.7553', 'rec': '0.8444', 'n': 495},
        'EndoScene CVC-300 (zero-shot)': {'dice': '0.7402', 'std': '0.1590', 'iou': '0.6098', 'prec': '0.6361', 'rec': '0.9427', 'n': 60},
        'PolypDB (All Modalities)': {'dice': '0.7283', 'std': '0.2544', 'iou': '0.6243', 'prec': '0.6889', 'rec': '0.8611', 'n': 7868},
        'ETIS-Larib (zero-shot)': {'dice': '0.0000', 'std': '0.0000', 'iou': '0.0000', 'prec': '0.0000', 'rec': '0.0000', 'n': 196},
    }

    # Parse HONEST_METRICS table
    honest_table = {}
    for line in honest.splitlines():
        if line.startswith('|') and not line.startswith('| Dataset') and not line.startswith('|---'):
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 6:
                dname = parts[0]
                n_img = int(parts[2])
                dice_val = float(parts[3])
                std_val = float(parts[4])
                iou_val = float(parts[5])
                honest_table[dname] = {
                    'n': n_img,
                    'dice': f"{dice_val:.4f}",
                    'std': f"{std_val:.4f}",
                    'iou': f"{iou_val:.4f}"
                }

    print("Parsed HONEST_METRICS:")
    for k, v in honest_table.items():
        print(f"  {k}: {v}")

    for k, d in mapping.items():
        raw = v5[k]
        rd = f"{raw['dice']:.4f}"
        rs = f"{raw['std']:.4f}"
        ri = f"{raw['iou']:.4f}"
        rp = f"{raw['precision']:.4f}"
        rr = f"{raw['recall']:.4f}"
        rn = raw['n']

        assert rd == d['dice'], f"Dice mismatch for {k}: {rd} vs {d['dice']}"
        assert rs == d['std'], f"Std mismatch for {k}: {rs} vs {d['std']}"
        assert ri == d['iou'], f"IoU mismatch for {k}: {ri} vs {d['iou']}"
        assert rp == d['prec'], f"Prec mismatch for {k}: {rp} vs {d['prec']}"
        assert rr == d['rec'], f"Rec mismatch for {k}: {rr} vs {d['rec']}"
        assert rn == d['n'], f"N mismatch for {k}: {rn} vs {d['n']}"

        # Check TeX
        assert d['dice'] in tex, f"dice {d['dice']} missing in TeX"
        assert d['std'] in tex, f"std {d['std']} missing in TeX"
        assert d['iou'] in tex, f"iou {d['iou']} missing in TeX"
        assert d['prec'] in tex, f"prec {d['prec']} missing in TeX"
        assert str(d['n']) in tex, f"N {d['n']} missing in TeX"

        # Check MD
        assert d['dice'] in md, f"dice {d['dice']} missing in MD"
        assert d['std'] in md, f"std {d['std']} missing in MD"
        assert d['iou'] in md, f"iou {d['iou']} missing in MD"
        assert d['prec'] in md, f"prec {d['prec']} missing in MD"
        assert d['rec'] in md, f"rec {d['rec']} missing in MD"

        print(f"[PASS] Verified: {k} (Dice: {rd} +/- {rs}, IoU: {ri}, Prec: {rp}, Rec: {rr}, N: {rn})")

    # Match honest_table entries to mapping
    match_honest = {
        'Kvasir-SEG': 'Kvasir-SEG (test split)',
        'HyperKvasir Segmented': 'HyperKvasir Segmented',
        'CVC-ClinicDB': 'CVC-ClinicDB (zero-shot)',
        'EndoScene CVC-300': 'EndoScene CVC-300 (zero-shot)',
        'PolypDB (All Modalities)': 'PolypDB (All Modalities)',
        'ETIS-Larib': 'ETIS-Larib (zero-shot)'
    }
    for h_name, m_name in match_honest.items():
        assert h_name in honest_table, f"Missing {h_name} in HONEST_METRICS table"
        ht = honest_table[h_name]
        md_expected = mapping[m_name]
        assert ht['dice'] == md_expected['dice'], f"HONEST_METRICS dice mismatch for {h_name}: {ht['dice']} vs {md_expected['dice']}"
        assert ht['std'] == md_expected['std'], f"HONEST_METRICS std mismatch for {h_name}: {ht['std']} vs {md_expected['std']}"
        assert ht['iou'] == md_expected['iou'], f"HONEST_METRICS iou mismatch for {h_name}: {ht['iou']} vs {md_expected['iou']}"
        assert ht['n'] == md_expected['n'], f"HONEST_METRICS N mismatch for {h_name}: {ht['n']} vs {md_expected['n']}"
        print(f"[PASS] HONEST_METRICS table entry {h_name} matches ground truth")

    print("\nALL VERIFICATIONS PASSED ACROSS 4 FILES!")

if __name__ == '__main__':
    test_cross_validation()
