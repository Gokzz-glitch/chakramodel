# Original User Request

## 2026-09-10T02:39:20Z

Decode the full architecture of the ChakraModel inch-by-inch, detailing every structural component (head, body, etc.) down to the tensor level to fully explain how the model processes data.

Integrity mode: development

Requirements:
### R1. Architectural Markdown Report
Create a comprehensive report at docs/ARCHITECTURE_DEEP_DIVE.md. The report must include Mermaid diagrams that map the entire data flow from the YOLO detection head, through the ViT-Large backbone ("body"), and out through the decoder heads, detailing the tensor shape transformations at each major step.

### R2. Parameter-Level Mapping
Generate a highly technical, parameter-level mapping (similar to a deep PyTorch summary()) that lists every layer, its parameter count, and exact input/output tensor shapes. Save this raw data to docs/parameter_mapping.txt or docs/parameter_mapping.csv.

### R3. Inline Code Annotation
Modify the core model source files in src/ (e.g., transformer_segmenter.py, chakranet_segmenter.py) by adding extensive inline comments. These comments must explicitly explain what each block of code does, referencing the "head", "body", or specific tensor transformations occurring at that exact line.

Acceptance Criteria:
### Programmatic Verification
- [ ] A programmatic check verifies that docs/ARCHITECTURE_DEEP_DIVE.md exists and contains at least one mermaid diagram block.
- [ ] A programmatic check verifies that docs/parameter_mapping.txt (or .csv) exists and contains tensor shape notation (e.g., [B, C, H, W]).
- [ ] A programmatic check (via git diff) verifies that the core model files in src/ have been modified to include new inline comments (e.g., lines starting with # or block docstrings).

### Independent Review
- [ ] An independent reviewer/auditor reviews the inline comments in the src/ files and confirms they provide "inch-by-inch" tensor-level explanations, rather than just generic docstrings.
