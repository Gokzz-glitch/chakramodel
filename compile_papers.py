import json
import os

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return "No abstract available."
    try:
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join([word for pos, word in word_positions])
        return abstract
    except:
        return "No abstract available."

def extract_summary(abstract):
    if not abstract:
        return "No summary available."
    sentences = [s.strip() for s in abstract.replace('?', '.').replace('!', '.').split('.') if s.strip()]
    return '. '.join(sentences[:2]) + ('.' if sentences else '')

markdown_content = "# Key Research Papers on Colonoscopy & AI\n\n"

# 1. OpenAlex (Highly Cited Foundational)
markdown_content += "## Foundational Papers (OpenAlex)\n\n"
try:
    with open('openalex.json', 'r', encoding='utf-8') as f:
        oa_data = json.load(f)
        for idx, item in enumerate(oa_data.get('results', [])):
            title = item.get('title', 'Unknown Title')
            authorships = item.get('authorships', [])
            author = authorships[0]['author']['display_name'] if authorships else "Unknown Author"
            if len(authorships) > 1:
                author += " et al."
            year = item.get('publication_year', 'Unknown Year')
            doi = item.get('doi', '')
            link = f"[DOI Link]({doi})" if doi else ""
            
            abstract_inv = item.get('abstract_inverted_index', {})
            abstract = reconstruct_abstract(abstract_inv)
            summary = extract_summary(abstract)
            
            markdown_content += f"### {idx+1}. {title}\n"
            markdown_content += f"- **Authors:** {author}\n"
            markdown_content += f"- **Publication Year:** {year}\n"
            markdown_content += f"- **Link:** {link}\n"
            markdown_content += f"- **Summary:** {summary}\n\n"
except Exception as e:
    markdown_content += f"Error processing OpenAlex data: {e}\n\n"

# 2. PubMed (Recent Advancements)
markdown_content += "## Recent Advancements (PubMed)\n\n"
try:
    with open('pubmed_abstracts.json', 'r', encoding='utf-8') as f:
        pm_data = json.load(f)
        for idx, item in enumerate(pm_data):
            title = item.get('title', 'Unknown Title')
            authors = item.get('authors', [])
            author = authors[0].get('name', 'Unknown Author') if authors else "Unknown Author"
            if len(authors) > 1:
                author += " et al."
            year = item.get('pub_date', 'Unknown Year')[:4] if item.get('pub_date') else 'Unknown'
            doi = item.get('doi', '')
            pmid = item.get('pmid', '')
            link = f"[DOI Link](https://doi.org/{doi})" if doi else (f"[PubMed Link](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)" if pmid else "")
            
            abstract = item.get('abstract', '')
            summary = extract_summary(abstract)
            
            markdown_content += f"### {idx+1}. {title}\n"
            markdown_content += f"- **Authors:** {author}\n"
            markdown_content += f"- **Publication Year:** {year}\n"
            markdown_content += f"- **Link:** {link}\n"
            markdown_content += f"- **Summary:** {summary}\n\n"
except Exception as e:
    markdown_content += f"Error processing PubMed data: {e}\n\n"

# 3. EuropePMC (Open Access)
markdown_content += "## Open Access Literature (Europe PMC)\n\n"
try:
    with open('europepmc.json', 'r', encoding='utf-8') as f:
        epmc_data = json.load(f)
        for idx, item in enumerate(epmc_data.get('results', [])):
            title = item.get('title', 'Unknown Title')
            author = item.get('authorString', 'Unknown Author')
            year = item.get('pubYear', 'Unknown Year')
            doi = item.get('doi', '')
            link = f"[DOI Link](https://doi.org/{doi})" if doi else ""
            
            abstract = item.get('abstractText', '')
            # Simple html tag stripping
            abstract = abstract.replace('<i>', '').replace('</i>', '').replace('<b>', '').replace('</b>', '')
            summary = extract_summary(abstract)
            
            markdown_content += f"### {idx+1}. {title}\n"
            markdown_content += f"- **Authors:** {author}\n"
            markdown_content += f"- **Publication Year:** {year}\n"
            markdown_content += f"- **Link:** {link}\n"
            markdown_content += f"- **Summary:** {summary}\n\n"
except Exception as e:
    markdown_content += f"Error processing Europe PMC data: {e}\n\n"

with open('colonoscopy_research_papers.md', 'w', encoding='utf-8') as f:
    f.write(markdown_content)

print("Generated colonoscopy_research_papers.md successfully.")
