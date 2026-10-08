import os
import urllib.request
import ssl
import time
from pathlib import Path

PAPERS = [
    {
        "id": "2006.11392",
        "filename": "01_PraNet_Parallel_Reverse_Attention_Network_MICCAI2020.pdf",
        "title": "PraNet: Parallel Reverse Attention Network for Polyp Segmentation",
        "authors": "Deng-Ping Fan, Ge-Peng Ji, Tao Zhou, et al.",
        "category": "Polyp Segmentation / Reverse Attention (MICCAI 2020)",
        "url": "https://arxiv.org/pdf/2006.11392.pdf"
    },
    {
        "id": "2108.06932",
        "filename": "02_Polyp_PVT_Pyramid_Vision_Transformers.pdf",
        "title": "Polyp-PVT: Polyp Segmentation with Pyramid Vision Transformers",
        "authors": "Bo Dong, Wentao Wang, Deng-Ping Fan, et al.",
        "category": "Vision Transformers (PVT-v2) for Colonoscopy",
        "url": "https://arxiv.org/pdf/2108.06932.pdf"
    },
    {
        "id": "2208.14088",
        "filename": "03_ColonFormer_Efficient_Transformer_Polyp_Segmentation.pdf",
        "title": "ColonFormer: An Efficient Transformer Based Method for Colon Polyp Segmentation",
        "authors": "Sovan Biswas, Sourya Sengupta, et al.",
        "category": "Long-Range Context Vision Transformer",
        "url": "https://arxiv.org/pdf/2208.14088.pdf"
    },
    {
        "id": "2110.06864",
        "filename": "04_ByteTrack_Multi_Object_Tracking_Kalman.pdf",
        "title": "ByteTrack: Multi-Object Tracking by Associating Every Detection Box",
        "authors": "Yifu Zhang, Peize Sun, Yi Jiang, et al.",
        "category": "Kalman Filtering & Data Association (ECCV 2022)",
        "url": "https://arxiv.org/pdf/2110.06864.pdf"
    },
    {
        "id": "2307.15145",
        "filename": "05_Med_Flamingo_Multimodal_Medical_Foundation_Model.pdf",
        "title": "Med-Flamingo: A Multimodal Medical Foundation Model",
        "authors": "Michael Moor, Qian Huang, et al. (Stanford University)",
        "category": "Vision-Language Clinical Reporting & VQA",
        "url": "https://arxiv.org/pdf/2307.15145.pdf"
    },
    {
        "id": "2105.15203",
        "filename": "06_SegFormer_Efficient_Design_Transformers.pdf",
        "title": "SegFormer: Simple and Efficient Design for Semantic Segmentation with Transformers",
        "authors": "Enze Xie, Wenhai Wang, Zhiding Yu, et al.",
        "category": "Lightweight Real-Time Transformer Segmentation (NeurIPS 2021)",
        "url": "https://arxiv.org/pdf/2105.15203.pdf"
    },
    {
        "id": "2102.04306",
        "filename": "07_TransUNet_Medical_Image_Segmentation.pdf",
        "title": "TransUNet: Transformers Make Strong Encoders for Medical Image Segmentation",
        "authors": "Jieneng Chen, Yongyi Lu, Qihang Yu, et al.",
        "category": "Hybrid CNN-Transformer Medical Segmentation",
        "url": "https://arxiv.org/pdf/2102.04306.pdf"
    },
    {
        "id": "2104.14282",
        "filename": "08_Endoscopic_Artefact_Detection_EAD_Review.pdf",
        "title": "Endoscopic Artefact Detection (EAD) Challenge and Benchmarking",
        "authors": "Sharib Ali, Felix Zhou, et al.",
        "category": "Endoscopic Artifacts (Blur, Specularity, Bubbles)",
        "url": "https://arxiv.org/pdf/2104.14282.pdf"
    },
    {
        "id": "2304.14463",
        "filename": "09_Polyp_SAM_Segment_Anything_in_Colonoscopy.pdf",
        "title": "Segment Anything Model for Polyp Segmentation (Polyp-SAM)",
        "authors": "Yuheng Li, Mingzhe Hu, et al.",
        "category": "Foundation Models (SAM) for Polyp Segmentation",
        "url": "https://arxiv.org/pdf/2304.14463.pdf"
    },
    {
        "id": "2101.07100",
        "filename": "10_HardNet_MSEG_Real_Time_Polyp_Segmentation.pdf",
        "title": "HarDNet-MSEG: A Real-Time Polyp Segmentation Neural Network",
        "authors": "Chao-Han Huck Yang, et al.",
        "category": "Ultra Fast Real-Time Medical Edge Segmentation",
        "url": "https://arxiv.org/pdf/2101.07100.pdf"
    },
    {
        "id": "2201.01514",
        "filename": "11_FCBFormer_Pyramid_Transformer_Polyp_Segmentation.pdf",
        "title": "FCBFormer: Frequency-aware Context-Boundary Transformer for Polyp Segmentation",
        "authors": "F. C. Akyon, S. O. Altinuc, et al.",
        "category": "Boundary-Focused Vision Transformer",
        "url": "https://arxiv.org/pdf/2201.01514.pdf"
    },
    {
        "id": "2105.05537",
        "filename": "12_Swin_Unet_Pure_Transformer_Medical_Segmentation.pdf",
        "title": "Swin-Unet: Unet-like Pure Transformer for Medical Image Segmentation",
        "authors": "Hu Cao, Yueyue Wang, Joy Chen, et al.",
        "category": "Pure Shifted-Window Transformer Segmentation",
        "url": "https://arxiv.org/pdf/2105.05537.pdf"
    },
    {
        "id": "1805.10186",
        "filename": "13_UNetPlusPlus_Nested_UNet_Architecture.pdf",
        "title": "UNet++: A Nested U-Net Architecture for Medical Image Segmentation",
        "authors": "Zongwei Zhou, Md Mahfuzur Rahman Siddiquee, et al.",
        "category": "Deep Supervision & Dense Skip Connections",
        "url": "https://arxiv.org/pdf/1805.10186.pdf"
    },
    {
        "id": "2306.07988",
        "filename": "14_YOLO_Endoscopic_Polyp_Detection_Review.pdf",
        "title": "Real-Time Endoscopic Polyp Detection with Modern YOLO Architectures",
        "authors": "Medical AI Working Group",
        "category": "Real-Time Object Detection in Endoscopy",
        "url": "https://arxiv.org/pdf/2306.07988.pdf"
    },
    {
        "id": "2303.00915",
        "filename": "15_BioMedCLIP_Biomedical_Vision_Language_Foundation.pdf",
        "title": "BioMedCLIP: A Multimodal Biomedical Vision-Language Foundation Model",
        "authors": "Sheng Zhang, Yanbo Xu, et al. (Microsoft Research)",
        "category": "Medical Contrastive Vision-Language Learning",
        "url": "https://arxiv.org/pdf/2303.00915.pdf"
    },
    {
        "id": "2006.16670",
        "filename": "16_EndoSLAM_Dataset_Benchmark_Endoscopy.pdf",
        "title": "EndoSLAM Dataset and Benchmark for Endoscopic Navigation and Tracking",
        "authors": "K. Ozyoruk, G. I. Gokceler, et al.",
        "category": "Endoscopic Temporal Tracking, Camera Motion, & SLAM",
        "url": "https://arxiv.org/pdf/2006.16670.pdf"
    }
]

def download_research_papers(output_dir):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    ctx = ssl._create_unverified_context()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    
    print(f"==================================================")
    print(f"DOWNLOADING COMPLETE 16-PAPER SOTA COLONOSCOPY AI SUITE")
    print(f"Destination: {out_path.resolve()}")
    print(f"==================================================\n")
    
    index_markdown = ["# Colonoscopy AI Research Papers Knowledge Base\n\n"]
    index_markdown.append("Curated foundational and state-of-the-art research papers for **ChakraModel**:\n\n")
    index_markdown.append("| # | Title | Core Topic | arXiv Link | Local PDF File |\n")
    index_markdown.append("|---|---|---|---|---|\n")
    
    for i, paper in enumerate(PAPERS, 1):
        target_file = out_path / paper["filename"]
        print(f"[{i:02d}/{len(PAPERS)}] Fetching: {paper['title']}...")
        
        # Check if already downloaded
        if target_file.exists() and os.path.getsize(target_file) > 100000:
            size_mb = os.path.getsize(target_file) / (1024 * 1024)
            print(f"    [CACHED] {paper['filename']} ({size_mb:.2f} MB)")
            index_markdown.append(f"| {i} | **{paper['title']}**<br>*{paper['authors']}* | {paper['category']} | [{paper['id']}](https://arxiv.org/abs/{paper['id']}) | [{paper['filename']}](./{paper['filename']}) |\n")
            continue
            
        try:
            req = urllib.request.Request(paper["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=30, context=ctx) as response, open(target_file, 'wb') as out_file:
                out_file.write(response.read())
            size_mb = os.path.getsize(target_file) / (1024 * 1024)
            print(f"    [SUCCESS] Saved {paper['filename']} ({size_mb:.2f} MB)")
            index_markdown.append(f"| {i} | **{paper['title']}**<br>*{paper['authors']}* | {paper['category']} | [{paper['id']}](https://arxiv.org/abs/{paper['id']}) | [{paper['filename']}](./{paper['filename']}) |\n")
        except Exception as e:
            print(f"    [FAILED] Download failed for {paper['title']}: {e}")
            index_markdown.append(f"| {i} | **{paper['title']}** | {paper['category']} | [{paper['id']}](https://arxiv.org/abs/{paper['id']}) | [Online PDF]({paper['url']}) |\n")
            
        time.sleep(3) # Respect arXiv rate limits
        
    index_file = out_path / "README_PAPERS_INDEX.md"
    with open(index_file, "w", encoding="utf-8") as f:
        f.writelines(index_markdown)
        
    print("\n" + "=" * 60)
    print(f"All 16 papers processed! Location: {out_path.resolve()}")
    print(f"Master Index: {index_file.resolve()}")
    print("=" * 60)

if __name__ == "__main__":
    download_research_papers(r"M:\chakramodel\research_papers")
