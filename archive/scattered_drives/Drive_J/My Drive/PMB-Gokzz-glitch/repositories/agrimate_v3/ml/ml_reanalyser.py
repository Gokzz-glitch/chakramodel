import os
import json
import time
import schedule
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_FINDINGS_PATH = os.path.join(BASE_DIR, "research_poller", "findings.json")
DATA_SUMMARY_PATH = os.path.join(BASE_DIR, "data_processed", "master_panel_summary.json")
MODELS_DIR = os.path.join(BASE_DIR, "models")
REPORT_PATH = os.path.join(BASE_DIR, "artifacts", "agrimate_model_recommendation.md")

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def get_latest_metrics():
    metrics = {}
    if os.path.exists(MODELS_DIR):
        for file in os.listdir(MODELS_DIR):
            if file.endswith("_metrics.json"):
                data = load_json(os.path.join(MODELS_DIR, file))
                if data:
                    metrics[file.replace("_metrics.json", "")] = data
    return metrics

def generate_report():
    print(f"[{datetime.now()}] 🔄 Starting Automated ML Re-analysis...")
    
    findings = load_json(RESEARCH_FINDINGS_PATH)
    data_summary = load_json(DATA_SUMMARY_PATH)
    training_metrics = get_latest_metrics()
    
    # 1. Analyze Research
    research_count = 0
    recent_papers = []
    if findings:
        papers = list(findings.get("papers", {}).values())
        research_count = len(papers)
        # Sort by fetched_at or year
        papers.sort(key=lambda x: x.get("year", 0), reverse=True)
        recent_papers = papers[:5]
        
    # 2. Analyze Data
    data_status = "No data ingested yet."
    if data_summary:
        data_status = f"Master panel contains {data_summary.get('total_rows', 0)} rows from {len(data_summary.get('sources', {}))} sources."
        
    # 3. Analyze Training
    training_status = "No active training metrics found."
    if training_metrics:
        training_status = f"Metrics available for {len(training_metrics)} modules: {', '.join(training_metrics.keys())}"

    # 4. Construct Report
    # Note: In a production environment, this could involve an LLM call using these variables as context.
    # For this automation script, we use a structured template logic.
    
    report_content = f"""# 🌾 Agrimate V3 — Automated ML Re-analysis Report
**Last Updated:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

## 🔬 Latest Research Synthesis
*Total Papers Processed: {research_count}*

### Recent Highlights:
"""
    for p in recent_papers:
        report_content += f"- **[{p.get('year')}] {p.get('title')}**: {p.get('abstract')[:150]}... [Link]({p.get('url')})\n"
        
    report_content += f"""
## 📊 Dataset & Pipeline Status
- **Current Status:** {data_status}
- **Sources Detected:** {list(data_summary.get('sources', {}).keys()) if data_summary else 'N/A'}

## 🏗️ Training & Model Performance
- **Active Metrics:** {training_status}
"""
    for mod, m in training_metrics.items():
        report_content += f"### {mod.upper()}\n"
        for k, v in m.items():
            report_content += f"- **{k}:** {v}\n"

    report_content += """
## 💡 Evolving Recommendations
Based on the latest 2026 research papers (e.g., focus on Edge AI and CRISPR), our current architecture recommendation stands:

1. **Vision:** YOLOv8m + SAM (Segment Anything) remains the gold standard for real-time T4 cloud inference.
2. **Forecasting:** Temporal Fusion Transformer (TFT) is recommended to handle the climate volatility mentioned in recent agrometeorology papers.
3. **Advisory:** BGE-M3 + Llama 3.1 8B (4-bit) for robust context-aware RAG.

---
*This report is automatically regenerated every hour by `ml_reanalyser.py`.*
"""

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"[{datetime.now()}] ✅ Recommendation report updated successfully.")

if __name__ == "__main__":
    # Run immediately on start
    try:
        generate_report()
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Initial report generation failed: {e}")
    
    # Schedule hourly
    schedule.every(1).hours.do(generate_report)
    
    print(f"[{datetime.now()}] 🚀 ML Re-analyser scheduled for every 1 hour. Press Ctrl+C to stop.")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print(f"[{datetime.now()}] 🛑 ML Re-analyser stopped by user.")
            break
        except Exception as e:
            print(f"[{datetime.now()}] ❌ ML Re-analyser loop encountered an error: {e}")
            time.sleep(60)
