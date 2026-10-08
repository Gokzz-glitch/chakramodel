from __future__ import annotations
from typing import Sequence


def temporal_consistency_score(gt_present: Sequence[int], pred_present: Sequence[int]) -> float:
    """
    TCS over one sequence:
    numerator: frames t where GT_t=1 and Pred_t=1 and Pred_{t-1}=1
    denominator: frames t where GT_t=1, for t=1..T-1
    """
    if len(gt_present) != len(pred_present):
        raise ValueError("gt_present and pred_present must have same length")
    if len(gt_present) < 2:
        return 0.0

    num, den = 0, 0
    for t in range(1, len(gt_present)):
        if int(gt_present[t]) == 1:
            den += 1
            if int(pred_present[t]) == 1 and int(pred_present[t - 1]) == 1:
                num += 1
    return (num / den) if den > 0 else 0.0


def temporal_consistency_score_multi(sequences: Sequence[tuple[Sequence[int], Sequence[int]]]) -> float:
    if not sequences:
        return 0.0
    vals = [temporal_consistency_score(gt, pred) for gt, pred in sequences]
    return sum(vals) / len(vals)
    