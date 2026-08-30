import csv
import os

def is_indian(contact):
    email = contact.get('Email', '').lower()
    affil = contact.get('Affiliation', '').lower()
    indian_domains = ['.in', 'iit', 'nit', 'aiims', 'bits', 'iiit', 'isb', 'iim']
    if any(d in email for d in indian_domains): return True
    indian_keywords = ['india', 'delhi', 'mumbai', 'bangalore', 'bengaluru', 'chennai', 'hyderabad', 'kolkata', 'pune', 'kanpur', 'kharagpur', 'madras', 'roorkee', 'guwahati']
    if any(k in affil for k in indian_keywords): return True
    return False

def get_leads():
    files = ['priority_5_foreign_and_top_institutions.csv', 'priority_1_colonoscopy_ai.csv', 'priority_2_endoscopy_ai.csv']
    contacted = set()
    if os.path.exists('linkedin_contacted.txt'):
        with open('linkedin_contacted.txt', encoding='utf-8') as f:
            contacted = set(l.strip().lower() for l in f if l.strip())
            
    indians = []
    foreign = []
    
    for file in files:
        if not os.path.exists(file): continue
        with open(file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                em = row.get('Email', '').strip().lower()
                name = row.get('Name', '').strip()
                track_key = em if em else name.lower()
                if not track_key or track_key in contacted: continue
                
                if is_indian(row):
                    if len(indians) < 20: indians.append(row)
                else:
                    if len(foreign) < 20: foreign.append(row)
                    
                if len(indians) == 20 and len(foreign) == 20:
                    break
        if len(indians) == 20 and len(foreign) == 20:
            break
            
    with open('manual_leads.md', 'w', encoding='utf-8') as out:
        out.write('# LinkedIn Outreach Batch (40 Leads)\n\n')
        out.write('Here are 20 Indian and 20 Foreign leads to message manually today.\n\n')
        out.write('## Note Template\n')
        out.write('**Note (Max 300 characters):**\n')
        out.write('> Hi [First Name], I\'m an AI undergrad building PolypNet-3D: a YOLOv8+Kalman pipeline hitting 49 FPS for real-time colonoscopy polyp detection. I admire your work and would love to connect to follow your research!\n\n')
        out.write('## Indian Leads (20)\n')
        for i, lead in enumerate(indians):
            out.write(f"{i+1}. **{lead.get('Name')}** - {lead.get('Affiliation')}\n")
        out.write('\n## Foreign Leads (20)\n')
        for i, lead in enumerate(foreign):
            out.write(f"{i+1}. **{lead.get('Name')}** - {lead.get('Affiliation')}\n")

if __name__ == '__main__':
    get_leads()
