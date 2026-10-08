import pytest
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from statistical_significance import StatisticalSignificance

def test_identical_arrays():
    """Test behavior when Model A and Model B have identical scores (Zero Variance)"""
    scores_a = np.array([0.90, 0.91, 0.92, 0.89, 0.88])
    scores_b = np.array([0.90, 0.91, 0.92, 0.89, 0.88])
    
    results = StatisticalSignificance.run_tests(scores_a, scores_b)
    
    assert results["significant"] == False
    assert results["wilcoxon_p"] == 1.0
    assert results["ttest_p"] == 1.0

def test_significant_improvement():
    """Test behavior when Model A is consistently better than Model B"""
    # Create deterministic scores
    scores_b = np.array([0.80, 0.82, 0.81, 0.79, 0.80, 0.85, 0.83, 0.82, 0.81, 0.80])
    # Model A is consistently +0.05 better
    scores_a = scores_b + 0.05
    
    results = StatisticalSignificance.run_tests(scores_a, scores_b)
    
    assert results["significant"] == True
    assert results["wilcoxon_p"] < 0.05
    assert results["ttest_p"] < 0.05

def test_confidence_interval():
    """Test 95% Confidence Interval calculation"""
    data = np.array([0.5, 0.6, 0.7, 0.55, 0.65])
    mean, ci = StatisticalSignificance.calculate_confidence_interval(data)
    
    assert np.isclose(mean, 0.6)
    assert ci > 0.0 # Standard error should exist

def test_mismatched_lengths():
    """Test that mismatched lengths raise an AssertionError"""
    scores_a = np.array([0.90, 0.91])
    scores_b = np.array([0.90])
    
    with pytest.raises(AssertionError):
        StatisticalSignificance.run_tests(scores_a, scores_b)
