# Original User Request

## Initial Request — 2026-08-29T07:13:55Z

Generate 6 independent, plug-and-play Kaggle `.ipynb` notebooks for the optimized ChakraModel combinations.

Working directory: m:\chakramodel\notebooks
Integrity mode: benchmark

## Requirements

### R1. Kaggle Notebook Generation
Create 6 standalone `.ipynb` Jupyter Notebooks (one for each of the 6 combinations). Each notebook must contain Markdown cells explaining the architecture and Python code cells that successfully train/evaluate the pipeline using maximum hardware specifications (YOLOv8x, ResNet-101, ViT-Large).

### R2. Dataset Accessibility
Each notebook must include the code cell required to seamlessly download and extract the Kvasir-SEG dataset into the Kaggle environment `/kaggle/working/data/kvasir-seg` so the user does not need to manually configure the data paths.

### R3. Max-Spec Configuration
The notebooks must omit VRAM-saving techniques. Batch sizes must be high (e.g., 32), workers maxed out, and backbones upgraded. For example, PraNet combos must use ResNet-101, and Transformer combos must use ViT-Large (vit_large_patch16_384).

### R4. Verification Constraints
The agent must verify that the dataset links work and that the `.ipynb` files are valid JSON. No syntax errors are permitted in the output files.

## Acceptance Criteria

### Execution & Formatting
- [ ] 6 separate `.ipynb` files exist in the `m:\chakramodel\notebooks` directory.
- [ ] Each `.ipynb` is a valid JSON file and can be parsed by `nbformat`.
- [ ] Each notebook contains a working download link/command for Kvasir-SEG.
- [ ] Each notebook utilizes the maximized model backbones (e.g. YOLOv8x, ResNet101, ViT-Large).
