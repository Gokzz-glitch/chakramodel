## 2026-08-29T07:16:18Z
You are Explorer 2 (PraNet & ChakraNet Max-Spec Architectures).
Your working directory is: m:\chakramodel\.agents\explorer_2
Scope document: m:\chakramodel\PROJECT.md

Objective:
Analyze the CNN and PraNet architectures across `src/pranet_segmenter.py`, `src/topo_loss.py`, `src/run_all_combos.py`, and `notebooks/` to blueprint Combos 1 through 5 with maximum hardware specifications (ResNet-101 backbone, YOLOv8x, batch size 32, num_workers=4, AMP FP16).

Tasks:
1. Inspect `src/pranet_segmenter.py`, `src/run_all_combos.py`, `src/topo_loss.py`, `notebooks/`.
2. Detail how to upgrade PraNet's backbone from ResNet-34/50 to ResNet-101 (`torchvision.models.resnet101`) with Receptive Field Blocks (RFB), Parallel Partial Decoder (PPD), and Reverse Attention (RA) modules.
3. Blueprint Combos 1 to 5:
   - Combo 1 (ChakraNet-Focal): YOLOv8x detection proposal + PraNet ResNet-101 + DiceFocalLoss + MC Dropout.
   - Combo 2 (Topo-ChakraNet): PraNet ResNet-101 + Persistent Homology / Topological Loss (Betti number regularization).
   - Combo 3 (AdaBN-ChakraNet): PraNet ResNet-101 + Test-Time Adaptive Batch Normalization for multi-hospital domain generalization.
   - Combo 4 (DiffusionAug-ChakraNet): Stable Diffusion v1.5 + ControlNet Canny + MC Dropout uncertainty-based synthetic data filtering + PraNet ResNet-101 retraining with batch size 32.
   - Combo 5 (Fed-ChakraNet): Federated Learning (FedAvg) across multi-center partitions (Kvasir, CVC, ETIS-Larib) with PraNet ResNet-101 and batch size 32.
4. Ensure all designs use batch size 32, num_workers=4, AMP FP16, and self-contained classes.
5. Write your full analysis and implementation blueprints to `m:\chakramodel\.agents\explorer_2\analysis.md`.
6. Write your handoff report to `m:\chakramodel\.agents\explorer_2\handoff.md`.
Update `progress.md` in your folder as you work. Send a message to your orchestrator when done.
