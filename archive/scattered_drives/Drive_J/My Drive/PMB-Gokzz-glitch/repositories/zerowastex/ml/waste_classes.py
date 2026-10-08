# ============================================================
# Zer0wasteX — Waste Class Taxonomy
# Aligned with Indian SWM Rules 2016 + BBMP / Chennai GWMC
# ============================================================

# 6 primary classes used for training and inference
WASTE_CLASSES = {
    0: "organic",       # food waste, leaf, coconut shell, banana peel
    1: "plastic",       # PET bottles, sachets, covers, cups, straws
    2: "paper",         # newspaper, cardboard, tetrapack, paper bags
    3: "metal",         # tin cans, foil, wire, utensils
    4: "glass",         # bottles, jars, broken glass
    5: "hazardous",     # batteries, e-waste, medical, paint, chemicals
}

# Human-readable labels for the dashboard
CLASS_LABELS = {
    "organic":   {"emoji": "🍌", "color": "#84cc16", "hindi": "जैविक",   "tamil": "கரிம"},
    "plastic":   {"emoji": "🧴", "color": "#38bdf8", "hindi": "प्लास्टिक", "tamil": "பிளாஸ்டிக்"},
    "paper":     {"emoji": "📰", "color": "#fbbf24", "hindi": "कागज़",    "tamil": "காகிதம்"},
    "metal":     {"emoji": "🥫", "color": "#94a3b8", "hindi": "धातु",    "tamil": "உலோகம்"},
    "glass":     {"emoji": "🍾", "color": "#a78bfa", "hindi": "कांच",    "tamil": "கண்ணாடி"},
    "hazardous": {"emoji": "☣️", "color": "#ef4444", "hindi": "खतरनाक",  "tamil": "அபாயகரமான"},
}

# Segregation correctness rules
# A bin marked as "dry" should NOT receive organic waste, etc.
SEGREGATION_RULES = {
    "wet_bin":  ["organic"],
    "dry_bin":  ["plastic", "paper", "metal", "glass"],
    "hazardous_bin": ["hazardous"],
}

# Quality scoring weights per class (how easily mis-sorted they are)
CLASS_DIFFICULTY = {
    "organic":   1.0,
    "plastic":   1.0,
    "paper":     0.9,
    "metal":     0.9,
    "glass":     0.8,
    "hazardous": 1.2,  # penalty multiplier for hazardous mis-sort
}
