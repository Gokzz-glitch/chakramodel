# Original User Request

## 2026-08-29T07:14:09Z

You are the Project Orchestrator for the ChakraModel Kaggle Notebooks task.

Working directory: m:\chakramodel\.agents\orchestrator
Workspace root: m:\chakramodel
User request: Please read m:\chakramodel\.agents\ORIGINAL_REQUEST.md

Your mission:
Decompose, plan, dispatch, and coordinate specialists to create 6 independent, plug-and-play Kaggle `.ipynb` notebooks in `m:\chakramodel\notebooks` for the 6 optimized ChakraModel combinations.

Key Requirements:
1. Kaggle Notebook Generation: 6 standalone `.ipynb` files in `m:\chakramodel\notebooks` (one per combo), each with Markdown documentation and complete runnable Python code cells.
2. Dataset Accessibility: Each notebook must seamlessly download and extract Kvasir-SEG dataset into `/kaggle/working/data/kvasir-seg`.
3. Max-Spec Configuration: Omit VRAM-saving techniques, high batch sizes (e.g. 32), max workers, upgraded backbones (e.g. YOLOv8x, ResNet-101, ViT-Large vit_large_patch16_384).
4. Verification: Validate dataset URLs/commands, verify that all 6 `.ipynb` files are valid JSON and parseable with `nbformat` without syntax errors.

Maintain your `plan.md`, `progress.md`, and `BRIEFING.md` in `m:\chakramodel\.agents\orchestrator/`.
When all milestones and verification are complete, notify me with your completion report so that the Victory Audit can be initiated.
