"""
Zer0wasteX — Negative-class dataset scraper
Uses SerpAPI Google Images to download waste imagery for vision model training.

Usage:
    python scraper.py --query "overflowing garbage bins Chennai" --num 100 --out-dir dataset/negative_class
    python scraper.py --query "clean sorted waste bin" --num 50 --out-dir dataset/positive_class

Requires:
    SERPAPI_API_KEY environment variable
"""

import os
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime


def scrape_google_images_serpapi(query: str, num_images: int, out_dir: str) -> dict:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("ERROR: SERPAPI_API_KEY environment variable not set.")
        return {}

    output_path = Path(out_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    params = {
        "engine": "google_images",
        "q": query,
        "api_key": api_key,
        "num": num_images,
        "safe": "off",
    }

    print(f"🔍 Searching SerpAPI: '{query}' — requesting {num_images} images...")

    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API Request failed: {e}")
        return {}

    image_results = data.get("images_results", [])
    print(f"✅ API returned {len(image_results)} results. Downloading...")

    manifest = {
        "query": query,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "total_requested": num_images,
        "total_returned": len(image_results),
        "downloaded": [],
        "failed": [],
    }

    safe_query = query.replace(" ", "_").replace("/", "_")[:40]

    for i, img in enumerate(image_results):
        img_url = img.get("original")
        if not img_url:
            manifest["failed"].append({"index": i, "reason": "no_original_url"})
            continue

        file_name = f"{safe_query}_{i:04d}.jpg"
        file_path = output_path / file_name

        try:
            img_data = requests.get(img_url, timeout=8).content
            with open(file_path, "wb") as f:
                f.write(img_data)

            manifest["downloaded"].append({
                "index": i,
                "file": str(file_path),
                "source_url": img_url,
                "size_bytes": len(img_data),
            })
            print(f"  [{i+1}/{len(image_results)}] ✅ {file_name} ({len(img_data)//1024} KB)")
        except Exception as e:
            manifest["failed"].append({"index": i, "url": img_url, "reason": str(e)})
            print(f"  [{i+1}/{len(image_results)}] ⚠️  Failed: {e}")

        time.sleep(0.1)  # gentle rate-limit

    # Save manifest
    manifest_path = output_path / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n📋 Manifest saved → {manifest_path}")
    print(f"   Downloaded: {len(manifest['downloaded'])}  |  Failed: {len(manifest['failed'])}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Zer0wasteX dataset scraper")
    parser.add_argument("--query", "-q", default="overflowing garbage bins Chennai",
                        help="Google Images search query")
    parser.add_argument("--num", "-n", type=int, default=100,
                        help="Number of images to download")
    parser.add_argument("--out-dir", "-o", default="dataset/negative_class",
                        help="Output directory for downloaded images")
    args = parser.parse_args()

    scrape_google_images_serpapi(
        query=args.query,
        num_images=args.num,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
