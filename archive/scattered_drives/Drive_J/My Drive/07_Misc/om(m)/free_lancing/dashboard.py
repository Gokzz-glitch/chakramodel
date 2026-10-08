import gradio as gr
import database
import subprocess
import threading
import time
import os
import sqlite3

DB_PATH = r"M:\free_lancing\campaign.db"

def get_dashboard_stats():
    try:
        total, followups = database.get_stats()
        
        # Get latest 5 leads
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT company, email, date_sent, status FROM outreach ORDER BY date_sent DESC LIMIT 5")
        recent = cursor.fetchall()
        conn.close()
        
        table_html = "<table style='width:100%; text-align:left; border-collapse: collapse;'><tr><th>Company</th><th>Email</th><th>Date</th><th>Status</th></tr>"
        for r in recent:
            table_html += f"<tr><td style='padding:8px; border-bottom:1px solid #ddd;'>{r[0]}</td><td style='padding:8px; border-bottom:1px solid #ddd;'>{r[1]}</td><td style='padding:8px; border-bottom:1px solid #ddd;'>{r[2]}</td><td style='padding:8px; border-bottom:1px solid #ddd;'>{r[3]}</td></tr>"
        table_html += "</table>"
        
        return f"🚀 **Total Initial Emails Sent:** {total}\n\n♻️ **Total Follow-Ups Sent:** {followups}", table_html
    except Exception as e:
        return f"Error loading stats: {e}", ""

def trigger_outreach():
    def run_script():
        subprocess.run(["python", r"M:\free_lancing\auto_mailer.py"], cwd=r"M:\free_lancing")
    
    thread = threading.Thread(target=run_script)
    thread.start()
    return "Outreach triggered in the background! Please check the command prompt for live logs."

with gr.Blocks() as demo:
    gr.Markdown("# 🚀 ML Outreach Master Dashboard")
    gr.Markdown("Monitor your automated DevRel/Recruiter campaigns, track follow-ups, and manage your AI-driven email pipelines.")
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Live Stats")
            stats_box = gr.Markdown(value="Loading...")
            refresh_btn = gr.Button("🔄 Refresh Stats")
        with gr.Column(scale=2):
            gr.Markdown("### Recent Activity")
            recent_table = gr.HTML(value="Loading...")
            
    with gr.Row():
        trigger_btn = gr.Button("🔥 Manually Trigger Daily Outreach Blast", variant="primary")
        status_txt = gr.Textbox(label="Status", interactive=False)
        
    refresh_btn.click(fn=get_dashboard_stats, outputs=[stats_box, recent_table])
    trigger_btn.click(fn=trigger_outreach, outputs=[status_txt])
    
    # Load on startup
    demo.load(fn=get_dashboard_stats, outputs=[stats_box, recent_table])

if __name__ == "__main__":
    database.init_db()
    demo.launch(inbrowser=True, theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"))
