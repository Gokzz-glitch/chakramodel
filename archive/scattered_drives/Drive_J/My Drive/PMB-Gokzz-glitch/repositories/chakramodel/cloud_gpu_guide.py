# 🌐 ChakraNet: Online GPU Setup Guide
# ====================================
# Which combinations go WHERE and HOW to set them up

# ════════════════════════════════════════════════════════════
# OPTION 1: KAGGLE (BEST FREE OPTION — 30 hrs/week, T4 GPU)
# OPTION 2: GOOGLE COLAB (Free tier — T4 GPU, limited hours)
# OPTION 3: LIGHTNING AI (80 free GPU hours on signup)
# ════════════════════════════════════════════════════════════

"""
QUICK DECISION TABLE:

┌──────────────────────┬──────────────┬─────────────┬──────────────┐
│ Platform             │ Free GPU     │ VRAM        │ Best For     │
├──────────────────────┼──────────────┼─────────────┼──────────────┤
│ Your RTX 3050        │ Unlimited    │ 4 GB        │ #1,#3,#6,#2  │
│ Kaggle (FREE)        │ 30 hrs/week  │ 16 GB (T4)  │ #4 Diffusion │
│ Colab Free (FREE)    │ ~4 hrs/day   │ 15 GB (T4)  │ #5 Federated │
│ Colab Pro (₹900/mo)  │ ~50 hrs/mo   │ 40 GB (A100)│ If free runs │
│ Lightning AI (FREE)  │ 80 hrs total │ 16 GB (T4)  │ Backup       │
└──────────────────────┴──────────────┴─────────────┴──────────────┘

RECOMMENDATION:
  → Use KAGGLE for Combination #4 (Diffusion) — 16GB T4, plenty of time
  → Use COLAB FREE for Combination #5 (Federated) — simpler, runs faster
  → Keep #1, #3, #6, #2 on your local RTX 3050
"""
