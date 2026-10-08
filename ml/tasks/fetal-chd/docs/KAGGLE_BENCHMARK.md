# Kaggle one-command comparison

There is no trustworthy universal list of 44 downloadable CHD checkpoints:
published papers often release code without weights, use different label
definitions, or restrict downloads. Do not fill the manifest with invented
URLs. Put the exact 44 checkpoints you are licensed to use in a CSV based on
`model_manifest.example.csv`.

After adding the real rows, run this single Kaggle cell:

```python
!pip install -q -r /kaggle/working/FETAL-CHD/requirements.txt && \
python /kaggle/working/FETAL-CHD/kaggle_benchmark.py \
  --data-root /kaggle/input/cardium \
  --manifest /kaggle/input/chd-model-manifest/models.csv \
  --expected-models 44 \
  --out /kaggle/working/benchmark_results.csv
```

The runner downloads and caches weights, loads each model, evaluates the same
CARDIUM patient split, and writes accuracy, sensitivity, specificity, F1, and
ROC-AUC to `benchmark_results.csv`. Failed or inaccessible models are recorded
as `status=failed`; they are never reported as benchmark scores.

Each model must produce either one logit or two-class logits. For models with a
custom architecture, export a TorchScript file or add a dedicated adapter
before comparing it. Use patient-level splits and identical preprocessing to
avoid leakage and incomparable results.
