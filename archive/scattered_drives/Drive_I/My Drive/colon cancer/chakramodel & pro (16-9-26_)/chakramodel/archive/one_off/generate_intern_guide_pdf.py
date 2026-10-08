import matplotlib.pyplot as plt
import networkx as nx
from fpdf import FPDF
import os

def create_diagram():
    G = nx.DiGraph()
    
    # Add nodes
    G.add_node("Input", pos=(0, 2))
    G.add_node("YOLOv8\nDetection", pos=(1, 3))
    G.add_node("ByteTrack\nTracking", pos=(1, 1))
    
    G.add_node("ViT-Large\nSegmentation", pos=(2, 2))
    G.add_node("Topo Loss", pos=(3, 2))
    
    G.add_node("Conformal\nCalibration", pos=(4, 2))
    G.add_node("Certified Mask\nOutput", pos=(5, 2))
    
    # Add edges
    G.add_edge("Input", "YOLOv8\nDetection")
    G.add_edge("YOLOv8\nDetection", "ByteTrack\nTracking")
    G.add_edge("ByteTrack\nTracking", "ViT-Large\nSegmentation")
    G.add_edge("ViT-Large\nSegmentation", "Topo Loss")
    G.add_edge("Topo Loss", "Conformal\nCalibration")
    G.add_edge("ByteTrack\nTracking", "Conformal\nCalibration") # Skip path
    G.add_edge("Conformal\nCalibration", "Certified Mask\nOutput")
    
    pos = nx.get_node_attributes(G, 'pos')
    
    plt.figure(figsize=(10, 5))
    nx.draw(G, pos, with_labels=True, node_size=4500, node_color="skyblue", 
            font_size=10, font_weight="bold", arrowsize=20)
            
    plt.title("ChakraModel Unified Architecture Diagram", size=15)
    plt.savefig("architecture_diagram.png", bbox_inches="tight")
    plt.close()

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "ChakraModel Intern Guide: Architecture & Files", align="C")
        self.ln(15)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def create_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "1. Architecture Diagram")
    pdf.ln(10)
    
    # Insert diagram
    if os.path.exists("architecture_diagram.png"):
        pdf.image("architecture_diagram.png", x=10, w=190)
        pdf.ln(90)
    
    pdf.set_font("Helvetica", "", 11)
    description = (
        "The ChakraModel framework is a colonoscopy polyp segmentation system. It combines "
        "YOLOv8 for high-speed frame detection and tracking, with a Vision Transformer (ViT-Large) "
        "for complex segmentation. Topological Polyp Loss ensures the model outputs single, solid "
        "shapes, and Conformal Calibration adds statistical safety guarantees by preventing false positives."
    )
    pdf.multi_cell(0, 6, description)
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "2. Where Things Are (File Directory Map)")
    pdf.ln(10)
    
    files_data = [
        ("src/ (Core Logic)", "Contains all the main Python scripts for training, inference, and losses."),
        ("  - src/infer_stream.py", "The real-time video inference engine. Runs the full model on live video."),
        ("  - src/chakranet_segmenter.py", "The core segmentation model definition."),
        ("  - src/run_all_combos.py", "Master script to train and run experimental combinations."),
        ("  - src/conformal_calibration.py", "Adds the safety layer to predictions."),
        ("  - src/topo_loss.py", "Loss function to enforce structural constraints (Betti numbers)."),
        ("notebooks/ (Kaggle)", "Contains 6 Jupyter Notebooks ready to be uploaded to Kaggle for training."),
        ("weights/ (Models)", "Where all the `.pth` and `.pt` model weights are saved after training."),
        ("data/ (Datasets)", "Contains clinical datasets like Kvasir-SEG, CVC-ClinicDB for evaluation."),
        ("README.md", "The main entry point explaining the project, combinations, and results."),
        ("ARCHITECTURE-SPINE.md", "Theoretical invariants defining the 'rules' of the architecture.")
    ]
    
    for title, desc in files_data:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, title, ln=1)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, desc)
        pdf.ln(4)
        
    pdf.output("Intern_Architecture_Guide.pdf")

if __name__ == "__main__":
    create_diagram()
    create_pdf()
    print("PDF generated successfully.")
