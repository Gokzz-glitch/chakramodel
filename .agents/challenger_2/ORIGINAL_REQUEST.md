## 2026-08-29T07:24:03Z
You are Challenger 2 (Adversarial Max-Spec & Dataset Stress Tester).
Your working directory is: m:\chakramodel\.agents\challenger_2
Scope document: m:\chakramodel\PROJECT.md

Objective:
Perform adversarial stress testing on the configurations, model backbones, and dataset acquisition logic across all 6 notebooks in `m:\chakramodel\notebooks/`:
1. `Combo1_ChakraNet_Focal.ipynb`
2. `Combo2_Topo_ChakraNet.ipynb`
3. `Combo3_AdaBN_ChakraNet.ipynb`
4. `Combo4_DiffusionAug_ChakraNet.ipynb`
5. `Combo5_Federated_ChakraNet.ipynb`
6. `Combo6_ChakraTransformer.ipynb`

Tasks:
1. Write and execute an adversarial test script that:
   - Asserts each notebook contains code for automated Kvasir-SEG download and target path `/kaggle/working/data/kvasir-seg`.
   - Asserts `batch_size=32` is configured in the training DataLoader across all notebooks.
   - Asserts `resnet101` is used in Combos 1-5, and `vit_large_patch16_384` is used in Combo 6.
   - Asserts that all model classes and loss functions are self-contained without imports of non-existent local modules.
2. Report comprehensive pass/fail results in `m:\chakramodel\.agents\challenger_2\handoff.md`.
Update `progress.md` as you work. Send a message to your orchestrator when done.
