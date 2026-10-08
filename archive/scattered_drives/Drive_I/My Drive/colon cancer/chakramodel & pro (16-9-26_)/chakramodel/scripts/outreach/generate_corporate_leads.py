import csv

COMPANIES = [
    ("Siemens Healthineers", "careers@siemens-healthineers.com", "Germany"),
    ("Philips Healthcare", "careers@philips.com", "Netherlands"),
    ("GE Healthcare", "careers@ge.com", "USA"),
    ("Medtronic", "careers@medtronic.com", "USA"),
    ("Intuitive Surgical", "jobs@intusurg.com", "USA"),
    ("Olympus Medical", "careers@olympus.com", "Japan"),
    ("Stryker", "careers@stryker.com", "USA"),
    ("Johnson & Johnson", "careers@jnj.com", "USA"),
    ("Boston Scientific", "careers@bsci.com", "USA"),
    ("Fujifilm Healthcare", "careers@fujifilm.com", "Japan"),
    ("Canon Medical", "careers@canon.com", "Japan"),
    ("Zebra Medical Vision", "hr@zebra-med.com", "Israel"),
    ("Aidoc", "careers@aidoc.com", "Israel"),
    ("Viz.ai", "careers@viz.ai", "USA"),
    ("Butterfly Network", "careers@butterflynetwork.com", "USA"),
    ("PathAI", "careers@pathai.com", "USA"),
    ("Proscia", "careers@proscia.com", "USA"),
    ("Paige.AI", "careers@paige.ai", "USA"),
    ("Tempus", "careers@tempus.com", "USA"),
    ("Freenome", "careers@freenome.com", "USA"),
    ("Owkin", "careers@owkin.com", "France"),
    ("Harrison.ai", "careers@harrison.ai", "Australia"),
    ("Lunit", "careers@lunit.io", "South Korea"),
    ("Vuno", "careers@vuno.co", "South Korea"),
    ("DeepX", "careers@deepx.co.jp", "Japan"),
    ("Enlitic", "careers@enlitic.com", "USA"),
    ("Arterys", "careers@arterys.com", "USA"),
    ("HeartFlow", "careers@heartflow.com", "USA"),
    ("Caption Health", "careers@captionhealth.com", "USA"),
    ("Qure.ai", "careers@qure.ai", "India"),
    ("Sigtuple", "careers@sigtuple.com", "India"),
    ("Tricog", "careers@tricog.com", "India"),
    ("Niramai", "careers@niramai.com", "India"),
    ("Artelus", "careers@artelus.com", "India"),
    ("Athelas", "careers@athelas.com", "USA"),
    ("Forward", "careers@goforward.com", "USA"),
    ("Babylon Health", "careers@babylonhealth.com", "UK"),
    ("Ada Health", "careers@ada.com", "Germany"),
    ("Kry", "careers@kry.se", "Sweden"),
    ("Halodoc", "careers@halodoc.com", "Indonesia"),
    ("Nvidia Healthcare", "careers@nvidia.com", "USA"),
    ("Google Health", "careers@google.com", "USA"),
    ("Microsoft Health", "careers@microsoft.com", "USA"),
    ("IBM Watson Health", "careers@ibm.com", "USA"),
    ("Apple Health", "careers@apple.com", "USA"),
    ("Meta AI", "careers@meta.com", "USA"),
    ("OpenAI", "careers@openai.com", "USA"),
    ("DeepMind", "careers@deepmind.com", "UK"),
    ("Anthropic", "careers@anthropic.com", "USA"),
    ("Hugging Face", "careers@huggingface.co", "USA"),
]

def generate():
    # Read any existing ones
    existing = []
    try:
        with open('corporate_leads.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.append(row)
    except FileNotFoundError:
        pass

    with open('corporate_leads.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Name', 'Email', 'Affiliation', 'Paper Title'])
        if not existing:
            writer.writeheader()
            
        for comp, email, country in COMPANIES:
            writer.writerow({
                'Name': 'Hiring Manager',
                'Email': email,
                'Affiliation': comp,
                'Paper Title': 'Paid Internship Inquiry'
            })
            
    print(f"Added {len(COMPANIES)} tier-1 MedTech and AI companies to corporate_leads.csv")

if __name__ == '__main__':
    generate()
