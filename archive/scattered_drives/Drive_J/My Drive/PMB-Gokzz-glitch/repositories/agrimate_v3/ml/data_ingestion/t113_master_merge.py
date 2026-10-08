"""
T-113: Master Panel Merge
Merges all Phase 1 output datasets into a single consolidated master parquet file.
"""
import os
import pandas as pd
import json


def run():
    print("=" * 60)
    print("  T-113: MASTER PANEL MERGE")
    print("=" * 60)

    data_dir = "data_processed"
    os.makedirs(data_dir, exist_ok=True)

    frames = []

    # T-101: APY Data
    apy_path = os.path.join(data_dir, "t101_apy_master.parquet")
    if os.path.exists(apy_path):
        apy = pd.read_parquet(apy_path)
        apy["data_source"] = "APY"
        frames.append(apy)
        print(f"  APY rows loaded    : {len(apy)}")
    else:
        print("  [WARN] APY parquet not found, skipping.")

    # T-103: Agmarknet Prices
    prices_path = os.path.join(data_dir, "t103_agmarknet_master.parquet")
    if os.path.exists(prices_path):
        prices = pd.read_parquet(prices_path)
        prices["data_source"] = "AGMARKNET"
        # Align schemas before concat
        for col in ["state_name", "district_name", "crop_year", "season", "crop", "area", "production", "yield"]:
            if col not in prices.columns:
                prices[col] = None
        frames.append(prices)
        print(f"  Price rows loaded  : {len(prices)}")
    else:
        print("  [WARN] Agmarknet parquet not found, skipping.")

    # T-108: RAG Chunks (count only, saved separately)
    rag_path = os.path.join(data_dir, "t108_rag_knowledge.jsonl")
    rag_count = 0
    if os.path.exists(rag_path):
        with open(rag_path, "r", encoding="utf-8") as f:
            rag_count = sum(1 for _ in f)
        print(f"  RAG chunks indexed : {rag_count}")

    if not frames:
        print("  [ERROR] No data to merge. Aborting.")
        return 1

    master = pd.concat(frames, ignore_index=True)
    master_path = os.path.join(data_dir, "agrimate_master_panel.parquet")
    master.to_parquet(master_path, engine="fastparquet", index=False)

    # Write summary JSON
    summary = {
        "total_rows": len(master),
        "rag_chunks": rag_count,
        "columns": list(master.columns),
        "sources": master["data_source"].value_counts().to_dict()
    }
    summary_path = os.path.join(data_dir, "master_panel_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Master Panel saved : {master_path}")
    print(f"  Total rows         : {len(master)}")
    print(f"  Summary saved      : {summary_path}")
    print("=" * 60)
    print("  T-113 COMPLETE - Ready for Phase 2 Model Training")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run())
