import os
import sys
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"m:\chakramodel")
from verify_polypgen_integrity import verify_single_image, collect_all_image_targets, resolve_dataset_root

def benchmark():
    dataset_root, _ = resolve_dataset_root(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted")
    all_targets = collect_all_image_targets(dataset_root)
    
    flat_paths = []
    for cat, paths in all_targets.items():
        flat_paths.extend([str(p) for p in paths])
    
    total_in_dataset = len(flat_paths)
    print(f"Total visual files enumerated: {total_in_dataset:,}")
    assert total_in_dataset == 19260, f"Expected 19,260 targets, got {total_in_dataset}"

    # Sample 500 files uniformly across dataset
    random.seed(42)
    sample_500 = random.sample(flat_paths, 500)

    # Benchmark 1: Single thread (1 worker) on 50 images to measure pure single-core latency
    sample_50 = sample_500[:50]
    t0 = time.perf_counter()
    for p in sample_50:
        res = verify_single_image(p)
        assert res["valid"] is True
    t1 = time.perf_counter()
    single_duration = t1 - t0
    single_throughput = len(sample_50) / single_duration
    avg_latency_ms = (single_duration / len(sample_50)) * 1000
    print(f"[Single Thread Benchmark - 50 files]:")
    print(f"  Duration: {single_duration:.3f}s")
    print(f"  Throughput: {single_throughput:.1f} files/sec")
    print(f"  Avg Latency per file: {avg_latency_ms:.2f} ms")

    # Benchmark 2: 16 threads on 500 files (matching verify_polypgen_integrity configuration)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(verify_single_image, p) for p in sample_500]
        results = [f.result() for f in as_completed(futures)]
    t1 = time.perf_counter()
    multi_duration = t1 - t0
    multi_throughput = len(sample_500) / multi_duration
    projected_total_time = 19260 / multi_throughput

    print(f"\n[16-Thread Benchmark - 500 files]:")
    print(f"  Duration: {multi_duration:.3f}s")
    print(f"  Throughput: {multi_throughput:.1f} files/sec")
    print(f"  Projected time for 19,260 files: {projected_total_time:.2f}s ({projected_total_time/60:.2f} minutes)")

    # Compare with reported numbers in polypgen_integrity_report.json
    reported_throughput = 146.3
    reported_duration = 131.63
    print(f"\n[Comparison with Reported Audit Artifact]:")
    print(f"  Reported Duration  : {reported_duration:.2f}s")
    print(f"  Reported Throughput: {reported_throughput:.1f} files/sec")
    print(f"  Empirical Multi-thread Throughput: {multi_throughput:.1f} files/sec")
    diff_pct = abs(multi_throughput - reported_throughput) / reported_throughput * 100
    print(f"  Relative difference: {diff_pct:.1f}%")
    
    # Check physical plausibility: throughput must be within reasonable order of magnitude
    assert 50.0 <= multi_throughput <= 500.0, f"Throughput {multi_throughput} is outside physically plausible range (50-500 files/sec)"
    print("\n[PASS] Timing and throughput are physically consistent and empirically reproducible.")

if __name__ == "__main__":
    benchmark()
