import os
import requests
import sqlite3
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

KEYWORDS = os.getenv("SEARCH_KEYWORDS", "medical imaging,deep learning,polyp detection,computer vision").split(',')
COUNTRIES = ["IN", "CN", "RU"]  # OpenAlex country codes for India, China, Russia

def setup_db():
    conn = sqlite3.connect('leads.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            author_name TEXT,
            institution TEXT,
            country TEXT,
            paper_title TEXT,
            paper_abstract TEXT,
            contacted INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def search_openalex(keyword):
    # Search works in last 2 years from specific countries
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(keyword)}&filter=publication_year:>2023,institutions.country_code:{'|'.join(COUNTRIES)}&per-page=50"
    print(f"Searching OpenAlex for '{keyword}'...")
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('results', [])
    print(f"Failed to fetch: {response.status_code}")
    return []

def main():
    conn = setup_db()
    c = conn.cursor()
    
    total_added = 0
    for kw in KEYWORDS:
        works = search_openalex(kw.strip())
        for work in works:
            paper_title = work.get('title', '')
            abstract_inverted = work.get('abstract_inverted_index', {})
            # Reconstruct abstract
            abstract = ""
            if abstract_inverted:
                word_index = []
                for word, positions in abstract_inverted.items():
                    for pos in positions:
                        word_index.append((pos, word))
                word_index.sort()
                abstract = " ".join([w[1] for w in word_index])
            
            # Extract authors
            authorships = work.get('authorships', [])
            for auth in authorships:
                author_id = auth['author'].get('id', '')
                author_name = auth['author'].get('display_name', '')
                
                institutions = auth.get('institutions', [])
                institution_name = institutions[0].get('display_name', '') if institutions else ''
                country = institutions[0].get('country_code', '') if institutions else ''
                
                if not author_name or not institution_name:
                    continue
                    
                # Insert if not exists
                c.execute('SELECT id FROM leads WHERE id = ?', (author_id,))
                if not c.fetchone():
                    c.execute('''
                        INSERT INTO leads (id, author_name, institution, country, paper_title, paper_abstract)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (author_id, author_name, institution_name, country, paper_title, abstract))
                    total_added += 1
    
    conn.commit()
    conn.close()
    print(f"Successfully added {total_added} new researchers to leads.db")

if __name__ == "__main__":
    main()
