from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors

def generate_pdf(filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = styles['Heading1']
    title_style.alignment = 1 # Center
    
    heading_style = styles['Heading2']
    heading_style.textColor = colors.darkblue
    
    sub_heading = styles['Heading3']
    sub_heading.textColor = colors.black
    
    body_style = styles['Normal']
    
    story = []
    
    # PAGE 1: Intro and Instructions
    story.append(Paragraph("Kaggle Dataset Upload Guide for ChakraModel", title_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Introduction", heading_style))
    story.append(Paragraph("This guide provides comprehensive instructions for uploading critical colonoscopy datasets to Kaggle. These datasets will be used to extensively test the ChakraModel (our YOLO-based + tracking polyp detection model). We have categorized the datasets into two groups: standard benchmarks to prove our state-of-the-art performance, and extremely difficult stress-test datasets to find the model's breaking points.", body_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("General Kaggle Upload Instructions", heading_style))
    instructions = [
        "1. Open the provided dataset URL in your browser and download the complete data archive.",
        "2. If the data is compressed, ensure you extract it locally to verify the contents before uploading.",
        "3. Go to Kaggle.com and sign in to your Kaggle account.",
        "4. In the left-hand menu, click on 'Create' and select 'New Dataset'.",
        "5. Enter the dataset title exactly as specified in the 'Naming Convention' field for each dataset.",
        "6. Drag and drop the dataset folder or files into the upload area.",
        "7. Ensure the dataset privacy is set to 'Private' so it's not publicly available.",
        "8. Once uploaded, navigate to the dataset's 'Settings' or 'Sharing' tab and share it directly with my Kaggle account."
    ]
    for inst in instructions:
        story.append(Paragraph(inst, body_style))
        story.append(Spacer(1, 6))
    
    story.append(PageBreak())
    
    # PAGE 2: Group A Datasets
    story.append(Paragraph("Group A: Prove We Are The Best (Standard Benchmarks)", heading_style))
    story.append(Paragraph("These datasets represent standard benchmarks, large-scale clean data, and video challenges where the ChakraModel is expected to achieve state-of-the-art results.", body_style))
    story.append(Spacer(1, 12))
    
    group_a = [
        {
            "name": "HyperKvasir", 
            "size": "~30+ GB (Total), ~100MB (Segmented Subset)", 
            "url": "https://datasets.simula.no/hyper-kvasir/", 
            "naming": "HyperKvasir_Polyp_Raw",
            "desc": "A massive extension of the Kvasir dataset, containing over 110,000 images and 374 videos. It includes a specific subset of 1,000 precisely segmented polyp images. We need this to benchmark against large-scale comprehensive gastrointestinal findings."
        },
        {
            "name": "SUN-SEG", 
            "size": "~10-15 GB", 
            "url": "http://sundatabase.org/", 
            "naming": "SUN_SEG_Polyp_Raw",
            "desc": "A high-quality video polyp segmentation dataset with 158,690 frames (49,136 positive). It includes rich annotations such as boundaries and polygons, which is perfect for testing our temporal tracking capabilities."
        },
        {
            "name": "LDPolypVideo", 
            "size": "~5-10 GB", 
            "url": "https://github.com/dashishi/LDPolypVideo-Benchmark", 
            "naming": "LDPolypVideo_Polyp_Raw",
            "desc": "This dataset includes 160 colonoscopy videos with 40,266 annotated frames, focusing on polyp detection across diverse environments. Crucial for video-level evaluation."
        },
        {
            "name": "EndoScene (CVC-300)", 
            "size": "~100 MB", 
            "url": "Search Kaggle or legacy CVC portals", 
            "naming": "EndoScene_CVC300_Polyp_Raw",
            "desc": "Often used as an 'unseen-domain' test set to evaluate if models overfit to their training distribution. Includes varying polyp morphologies like flat and peduncular."
        }
    ]
    
    for item in group_a:
        story.append(Paragraph(f"Dataset: {item['name']}", sub_heading))
        story.append(Paragraph(f"<b>Description:</b> {item['desc']}", body_style))
        story.append(Paragraph(f"<b>Estimated Size:</b> {item['size']}", body_style))
        story.append(Paragraph(f"<b>URL:</b> <a href='{item['url']}' color='blue'>{item['url']}</a>", body_style))
        story.append(Paragraph(f"<b>Naming Convention:</b> {item['naming']}", body_style))
        story.append(Spacer(1, 12))
        
    story.append(PageBreak())
    
    # PAGE 3: Group B Datasets
    story.append(Paragraph("Group B: Find Where We Fail (Stress Tests)", heading_style))
    story.append(Paragraph("These datasets include multi-modal imaging, difficult lighting, narrow-band imaging, and un-prepped colons designed specifically to stress-test our model.", body_style))
    story.append(Spacer(1, 12))
    
    group_b = [
        {
            "name": "PICCOLO Dataset", 
            "size": "~1-2 GB", 
            "url": "https://zenodo.org/record/4630983", 
            "naming": "PICCOLO_Dataset_Polyp_Raw",
            "desc": "Designed specifically for difficult modalities. Contains 3,433 annotated images across White-Light Imaging (WLI) and Narrow-Band Imaging (NBI). Excellent for testing against complex optical enhancements."
        },
        {
            "name": "PolypDB", 
            "size": "~2 GB", 
            "url": "https://osf.io/pr7ms/", 
            "naming": "PolypDB_Polyp_Raw",
            "desc": "A multi-center dataset containing 3,934 images across five different imaging modalities (WLI, NBI, LCI, BLI, FICE). This is the ultimate stress test for multi-modal generalization."
        }
    ]
    
    for item in group_b:
        story.append(Paragraph(f"Dataset: {item['name']}", sub_heading))
        story.append(Paragraph(f"<b>Description:</b> {item['desc']}", body_style))
        story.append(Paragraph(f"<b>Estimated Size:</b> {item['size']}", body_style))
        story.append(Paragraph(f"<b>URL:</b> <a href='{item['url']}' color='blue'>{item['url']}</a>", body_style))
        story.append(Paragraph(f"<b>Naming Convention:</b> {item['naming']}", body_style))
        story.append(Spacer(1, 12))
        
    doc.build(story)

if __name__ == '__main__':
    generate_pdf('Kaggle_Dataset_Upload_Guide.pdf')
    print("Multi-page PDF generated successfully.")
