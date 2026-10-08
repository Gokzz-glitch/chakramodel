import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from t101_apy_ingestion import APYIngestor
from t103_agmarknet_scraper import run_scraper as run_agmarknet
from t108_knowledge_scraper import KnowledgeScraper


def run_pipeline():
    print("===========================================================")
    print("      AGRIMATE V3: PHASE 1 DATA INGESTION PIPELINE ")
    print("===========================================================\n")

    try:
        apy = APYIngestor(output_dir="data_processed")
        apy.fetch_data()
    except Exception as e:
        print(f"[ERROR] Failure in T-101 APY Pipeline: {e}")

    try:
        run_agmarknet()
    except Exception as e:
        print(f"[ERROR] Failure in T-103 Agmarknet Pipeline: {e}")

    try:
        rag = KnowledgeScraper(output_dir="data_processed")
        rag.simulate_vikaspedia_scrape()
    except Exception as e:
        print(f"[ERROR] Failure in T-108 Knowledge Extraction: {e}")

    print("\n===========================================================")
    print("      ALL PHASE 1 PIPELINES EXECUTED.                      ")
    print("      Ready for Master Parquet Merge (T-113)               ")
    print("===========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline())
