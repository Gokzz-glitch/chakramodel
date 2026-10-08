import os
import json
import uuid
import re


class KnowledgeScraper:
    """
    T-108: Knowledge Scraper for RAG Pipeline.
    """
    def __init__(self, output_dir="data_processed"):
        self.output_dir = output_dir
        self.output_file = os.path.join(self.output_dir, "t108_rag_knowledge.jsonl")
        os.makedirs(self.output_dir, exist_ok=True)

    def _clean_text(self, text):
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def chunk_document(self, content, title, source, max_chunk_size=500):
        sentences = content.split(". ")
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_chunk_size:
                current_chunk += sentence + ". "
            else:
                chunks.append({"id": str(uuid.uuid4()), "title": title, "source": source, "text": self._clean_text(current_chunk)})
                current_chunk = sentence + ". "
        if current_chunk:
            chunks.append({"id": str(uuid.uuid4()), "title": title, "source": source, "text": self._clean_text(current_chunk)})
        return chunks

    def simulate_vikaspedia_scrape(self):
        print("\nInitiating T-108: RAG Knowledge Extraction...")
        mock_htmls = [
            {"title": "Pest Management in Tomatos", "source": "Vikaspedia PDF", "content": "Tomatos are highly susceptible to early blight. Early blight is caused by the fungus Alternaria solani. It appears as dark concentric rings on older leaves. To prevent this ensure proper crop rotation. Apply Chlorothalonil fungicide at standard rates. Do not overwater as humidity speeds the fungal spread."},
            {"title": "Wheat Seed Choice", "source": "ICAR Bulletin 2023", "content": "The HD 3226 wheat variety is highly resistant to yellow rust. It is best sown in November. Seed rate is 40kg per acre. It requires 4 to 5 irrigations during the crop cycle. The yield potential is around 25 to 30 quintals per hectare. Apply Nitrogen primarily during the tillering stage."}
        ]
        all_chunks = []
        for doc in mock_htmls:
            all_chunks.extend(self.chunk_document(doc["content"], doc["title"], doc["source"]))
        with open(self.output_file, "w", encoding="utf-8") as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        print(f"T-108 Complete! RAG chunks saved to: {self.output_file}")


if __name__ == "__main__":
    scraper = KnowledgeScraper()
    scraper.simulate_vikaspedia_scrape()
