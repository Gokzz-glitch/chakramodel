# Serving

> Packaging and runtime for inference.

| | |
|---|---|
| Path | `ml/serving/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Packaging and runtime for inference.

## What does NOT belong here

- Training code.

## Contents

| Folder | Purpose |
|---|---|
| [`export/`](export/README.md) | Export to portable formats (e.g. ONNX) with parity tests. |
| [`runtime/`](runtime/README.md) | Inference runtime used by services and edge devices. |
| [`edge-optimization/`](edge-optimization/README.md) | Quantisation, pruning and device-specific tuning. |
| [`benchmarks/`](benchmarks/README.md) | Latency, throughput and memory benchmarks per target hardware. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
