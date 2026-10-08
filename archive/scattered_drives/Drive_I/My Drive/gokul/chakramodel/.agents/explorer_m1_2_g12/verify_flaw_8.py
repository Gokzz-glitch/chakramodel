import sys

# Canonical formula from src/conformal/conformal_calibration.py
def nonconformity_pos_canonical(mean_prob, variance):
    return (1.0 - mean_prob) + variance

def nonconformity_neg_canonical(mean_prob, variance):
    return mean_prob + variance

# Buggy inference formula from src/models/chakranet_segmenter.py (lines 343-344, 460-461)
def nonconformity_pos_inference_buggy(prob_resized, variance):
    return 1.0 - (prob_resized + variance)

def nonconformity_neg_inference_buggy(prob_resized, variance):
    return prob_resized - variance

test_cases = [
    (0.8, 0.1),
    (0.5, 0.2),
    (0.2, 0.15),
    (0.9, 0.05)
]

print("=== Flaw 8 Formula Comparison ===")
for p, v in test_cases:
    c_pos = nonconformity_pos_canonical(p, v)
    b_pos = nonconformity_pos_inference_buggy(p, v)
    c_neg = nonconformity_neg_canonical(p, v)
    b_neg = nonconformity_neg_inference_buggy(p, v)
    print(f"p={p:.2f}, v={v:.2f}:")
    print(f"  Pos: Canonical=(1-p)+v={c_pos:.4f} vs Buggy=1-(p+v)={b_pos:.4f} (Diff={c_pos - b_pos:.4f} = 2*v)")
    print(f"  Neg: Canonical=p+v={c_neg:.4f}     vs Buggy=p-v={b_neg:.4f}     (Diff={c_neg - b_neg:.4f} = 2*v)")
