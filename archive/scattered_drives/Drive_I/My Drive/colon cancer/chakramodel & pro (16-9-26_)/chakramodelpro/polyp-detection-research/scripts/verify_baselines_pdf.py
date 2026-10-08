import urllib.request
import fitz  # PyMuPDF
import tempfile
import sys

papers = {
    "P01": {
        "arxiv": "1911.07069",
        "metrics": ["0.8264", "0.7177", "0.7814", "0.6399"]
    },
    "P03": {
        "arxiv": "2006.11392",
        "metrics": ["0.898", "0.840", "0.885", "50", "0.899", "0.849", "0.896", "0.712", "0.640", "0.628", "0.567", "0.871", "0.797"]
    },
    "P04": {
        "arxiv": "2011.07631",
        "metrics": ["0.8206", "0.8100", "0.8000", "182", "0.8264", "0.8130"]
    },
    "P05": {
        "arxiv": "2108.00882",
        "metrics": ["0.904", "0.847", "0.916", "0.859", "0.753", "0.670", "0.750", "0.654", "0.888", "0.815", "72"]
    },
    "P08": {
        "arxiv": "2410.02528",
        "metrics": ["0.826", "0.822"]
    }
}

def verify_paper(pid, data):
    url = f"https://arxiv.org/pdf/{data['arxiv']}.pdf"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    print(f"\n--- Verifying {pid} ({url}) ---")
    try:
        with urllib.request.urlopen(req) as response:
            pdf_data = response.read()
            
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_data)
            tmp_path = tmp.name
            
        doc = fitz.open(tmp_path)
        text = ''
        for page in doc:
            text += page.get_text()
            
        mismatches = []
        for m in data['metrics']:
            if m in text:
                print(f"  [MATCH] {m}")
            else:
                print(f"  [MISSING] {m}")
                mismatches.append(m)
                
        if not mismatches:
            print(f"--> {pid} VERDICT: PERFECT MATCH")
        else:
            print(f"--> {pid} VERDICT: MISMATCH found for {mismatches}")
            
    except Exception as e:
        print(f"Failed to fetch or parse {pid}: {e}")

for pid, data in papers.items():
    verify_paper(pid, data)
