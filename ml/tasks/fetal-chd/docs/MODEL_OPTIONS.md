# Pretrained Model Options

These are two research models suitable for fetal ultrasound and congenital heart
disease (CHD) work.

## 1. FetalCLIP

- Repository: <https://github.com/BioMedIA-MBZUAI/FetalCLIP>
- Purpose: fetal-ultrasound visual-language foundation model and feature
  extractor
- Best fit: fine-tuning a CHD/Non-CHD classifier with the CARDIUM images
- Strength: pretrained specifically on fetal ultrasound data and evaluated on
  CHD detection
- Integration: use the repository's checkpoint/download instructions, extract
  image features, and train a binary classification head on the CARDIUM labels

FetalCLIP is the recommended starting point for this repository. It is a
foundation model rather than a guaranteed plug-and-play binary classifier, so
the final CHD head must be trained or fine-tuned on labeled data.

## 2. FM-DACL

- Repository: <https://github.com/13204942/FM-DACL>
- Purpose: fetal-heart ultrasound segmentation and multi-label diagnosis
- Best fit: projects requiring both cardiac-structure masks and diagnosis
- Strength: combines foundation-model representations with segmentation and
  classification
- Integration: convert the CARDIUM data to the repository's FETUS `.h5`
  format, then follow its checkpoint and inference commands

FM-DACL is the better option when segmentation is required, but it is more
complex than a binary image classifier and is not directly compatible with the
current CARDIUM folder layout.

## Important evaluation note

Model confidence for one image is not model accuracy. Evaluate either model on
a patient-level held-out test set and report accuracy, sensitivity, specificity,
F1, and ROC-AUC before using the results clinically.

The local `image_encoder.tar(CHd).gz` checkpoint already integrated into
`inference.py` remains the most direct option for the current CARDIUM pipeline.
