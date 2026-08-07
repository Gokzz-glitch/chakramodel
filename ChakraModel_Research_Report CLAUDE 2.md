# ChakraModel Research Brief: Colonoscopy Polyp Detection Landscape
### Independent verification pass — Tata Centre 36-hour hackathon (deadline Aug 1)

**Note on methodology:** This report was built from live web search and direct verification of primary sources (GitHub repos, dataset pages, papers) rather than reused from a prior draft. Several claims that circulate in AI-generated research briefs on this exact topic turned out to be wrong or misleading when checked against the actual source — those corrections are flagged explicitly below, because they materially change what your team should do in the first four hours.

---

## Executive Summary

Colonoscopy AI detection has one dominant, well-solved sub-problem (static-frame detection via YOLO, >90% mAP50 on Kvasir-SEG is routine) and one open, unsolved sub-problem (robust real-time detection on live, artifact-heavy video, which is why commercial CADe adoption is still limited). Your original ChakraModel idea — YOLOv8 for proposals + R-CNN for refinement — is a bad fit for 36 hours, not primarily because R-CNN is "unfeasible" in the abstract, but because two-stage pipelines add latency and custom glue code for a benefit (a few points of precision) you can get cheaper elsewhere.

**Recommended pivot, verified as buildable with public tools:**
- Single-stage detector: YOLOv8 (or v11), fine-tuned on Kvasir-SEG + CVC-ClinicDB. This is genuinely plug-and-play — confirmed via Ultralytics' own docs.
- Temporal stability: Ultralytics' native `model.track(tracker="bytetrack.yaml", persist=True)`, confirmed as a real, documented, one-line API — not a claim requiring correction.
- Artifact robustness: Albumentations-based augmentation (MotionBlur, CoarseDropout, RandomBrightnessContrast) during training — free, no architecture changes.
- Custom metrics (temporal consistency, artifact false-positive rate) as your differentiator, since these are exactly the axes reviewers of medical AI complain the standard mAP/IoU metrics ignore.

**What I had to correct from the "standard" version of this research brief that keeps circulating (and that your uploaded documents also contained, identically, three times in a row):**

1. **AVPDN's pretrained weights are NOT publicly available.** The GitHub repo (`xiaochen925/AVPDN`) explicitly says to "download the pre-trained model weights from the release page (**or contact the author for reasonable requests**)" — and the repo has **no releases published**. It also has 0 stars and 5 commits, is a single-author academic drop tied to one arXiv/Sci-Reports paper, and its documented hardware requirement is an **RTX 4090D with ≥24GB VRAM** — that will not run on a free Colab T4 (16GB), let alone within a 36-hour hackathon budget. Treat AVPDN as **read-only inspiration**, not an integration candidate.

2. **CVC-ClinicVideoDB (the actual name — "CVC-VideoClinicDB" is a common misspelling) is not casually downloadable.** It's a GIANA/MICCAI challenge dataset. To get it you must **contact the GIANA challenge organizers directly** — there is no self-serve Kaggle or GitHub mirror with the actual video files and ground truth. (The Kaggle link commonly cited for this — `balraj98/cvcclinicdb` — is the *static-image* CVC-ClinicDB, a different 612-image dataset from a different challenge track. Multiple papers and even the AVPDN repo itself conflate these two.) Budgeting "~30 minutes via Kaggle" for this dataset is wrong and will burn hours of your hackathon chasing a registration email that may not get answered in time.

3. **ECC-PolypDet's weights being gated behind Baidu Drive is accurate** — I confirmed this is a known, commonly-cited accessibility problem for this exact repo. Correctly deprioritized.

4. The **99.37% mAP@0.5 YOLOv11-on-Kvasir-SEG figure** that circulates is very likely a specific optimized-configuration result, not a typical out-of-box number — the broader literature I checked converges much more consistently around **90–96% mAP50** for stock YOLOv8/v11/v12 fine-tuned on Kvasir-SEG. Set your expectations there, not at 99%.

**Bottom line for the 36-hour build:** everything in the "keep" list below is real and buildable. The one piece of the standard plan that will actually blow your schedule is the video dataset acquisition step — fix that first (see Available Resources, dataset section) or you lose the whole afternoon of Day 1 waiting on a registration email.

---

## Existing Approaches — Ranked by Real Implementation Speed

| Approach | Core method | Verified benchmark | Code/weights public? | Integration time (verified) |
|---|---|---|---|---|
| **Ultralytics YOLOv8/v11/v12** | Single-stage, anchor-free CNN | 90–96% mAP50 on Kvasir-SEG across multiple independent papers (Sahoo et al. 2025, YOLO-LAN 2025, Lalinia & Sahafi 2024) | **Yes** — `pip install ultralytics`, COCO-pretrained weights auto-download | 1–3 hrs to first fine-tune run |
| **YOLOv8 + ByteTrack (native)** | Detector + Kalman-filter tracker, IDs persist across frames | N/A (tracking add-on, not a detector) | **Yes** — built into the `ultralytics` package, one kwarg | ~30 min once detector is trained |
| **AVPDN (RT-DETR-based)** | Dual-branch attention for motion blur + scale variance | 95.7% AP / 53.2 FPS on CVC-VideoClinicDB (self-reported, single paper, not independently reproduced) | **Code yes, pretrained weights NO** (must email author) | Not viable in 36h — budget 10+ hrs even before the weights problem, and you'd likely end up training their architecture from scratch on a 4090-class GPU you don't have on free Colab |
| **Faster R-CNN + temporal ROI (Qadir et al. style)** | Two-stage detector with hand-built temporal attention over sliding window | High precision, <20 FPS in original papers | Generic Faster R-CNN yes (torchvision); the temporal ROI module: no | Not viable — this is the original ChakraModel idea; custom tensor-level engineering, correctly cut |
| **ECC-PolypDet** | CenterNet + box-assisted contrastive learning | Strong on concealed/occluded polyps | Code yes, weights on Baidu Drive (access friction confirmed) | Not viable — training a contrastive loss from scratch in a hackathon is high-risk regardless of weight access |

**Why this ranking holds up:** the YOLO ecosystem's advantage isn't just speed, it's that Ultralytics ships pretrained weights, a stable Python API, and tracker integration as one product — every other option on this list requires you to either train from scratch or beg an academic author for a checkpoint over email during your hackathon window.

---

## Why Progress Stalls in This Field (verified, not just asserted)

- **Domain shift from static to video is real and well-documented.** Models trained purely on Kvasir-SEG/CVC-ClinicDB (curated, well-lit, centered still frames) degrade on live video because of motion blur, specular reflection, and water-washout — this is the stated motivation for AVPDN, LDPolypVideo, and multiple other papers independently, so it's a consensus finding, not one lab's framing.
- **Video ground-truth data is the actual bottleneck, not model architecture.** The best fully-annotated video datasets are either gated (CVC-ClinicVideoDB — contact required) or comparatively small (CVC-ClinicVideoDB: 18 videos; LDPolypVideo: 160 videos, openly available — see below). This is a bigger practical obstacle for a hackathon than any modeling choice.
- **Two-stage / heavy temporal architectures (3D-CNN, spatio-temporal transformers) are computationally expensive**, and hospitals run on modest embedded hardware — real-time deployment research consistently pushes toward lightweight single-stage detectors for this reason, which independently supports dropping the R-CNN stage.

---

## Alternative Directions — 36-Hour Feasibility

| Direction | Feasibility | Verified basis |
|---|---|---|
| **ByteTrack / BoT-SORT tracking wrapper** | **Feasible.** Confirmed as a native, one-argument Ultralytics feature (`tracker="bytetrack.yaml", persist=True`), well-documented with public config files (`track_high_thresh`, `track_buffer`, `match_thresh` all exposed and tunable). | High confidence |
| **Albumentations-based artifact augmentation** (MotionBlur, CoarseDropout, OpticalDistortion) | **Feasible.** Standard, free, well-documented library; no architecture change needed. | High confidence |
| **Custom short-term "bounding box persistence" logic on top of tracker output** (hold last-known box for N missing frames) | **Feasible**, and this is genuinely your best differentiation opportunity — it's a ~50-line Python wrapper around `model.track()` output, not a research contribution, but it directly targets the flicker/cognitive-fatigue problem that's repeatedly cited as a clinical adoption barrier. | Sound engineering plan |
| **AVPDN-style dual-attention architecture, built from scratch** | **Not feasible.** Even with the paper's method description, replicating a custom RT-DETR variant with novel attention modules in a hackathon is unrealistic regardless of weight access. | Correctly deprioritized |
| **Optical flow motion compensation** | **Not feasible** in 36h — adds a second heavy model and a fusion step with no off-the-shelf, plug-and-play library that does exactly this for detection (not just registration). | Correctly deprioritized |
| **Diffusion-based synthetic data generation (ControlPolypNet-style)** | **Not feasible** to train from scratch; **the underlying idea is worth stealing cheaply** via Albumentations instead, as above. | Reasonable compromise |

---

## Available Resources — Corrected

### Datasets

| Dataset | What it actually is | Access reality (verified) | Recommendation |
|---|---|---|---|
| **Kvasir-SEG** | 1,000 static images + segmentation masks | Freely downloadable in minutes via Kaggle (`debeshjha1/kvasirseg`) or HuggingFace | **Use — primary training set** |
| **CVC-ClinicDB** | 612 static images + masks, 29 sequences | Freely downloadable in minutes via Kaggle (`balraj98/cvcclinicdb`) — Research/educational use only | **Use — combine with Kvasir-SEG for training** |
| **CVC-ClinicVideoDB** ("CVC-VideoClinicDB") | 18 SD videos, 11,954 annotated frames, from the GIANA/MICCAI 2017 challenge | **Requires contacting GIANA challenge organizers directly** — no confirmed self-serve download link exists. Do not budget "30 minutes" for this. | **Do not depend on this for Day 1.** If access doesn't come through fast, skip it. |
| **LDPolypVideo** | 160 videos, 40,266 frames, ~4x larger than CVC-ClinicVideoDB and openly hosted | **Freely available now**, directly from the official GitHub repo (`dashishi/LDPolypVideo-Benchmark`) | **Use this as your video/temporal evaluation set instead of CVC-ClinicVideoDB.** It's bigger, more diverse, and — critically — you can actually get it before your deadline. |
| **PolypGen** | Multi-center dataset (6 clinical centers), useful for generalization testing | Available via academic portals/Synapse; access process not as instant as Kaggle | Optional stretch goal, not Day-1 critical path |
| **HyperKvasir** | 110,079 images, 373 videos | Large; openly available (CC-BY 4.0) but selective downloading needed given size | Use selectively for negative/hard-case mining if time allows |

### Pretrained Models

| Model | Verified availability | Integration effort |
|---|---|---|
| Ultralytics YOLOv8/v11 (COCO-pretrained) | Yes — auto-downloads on first `YOLO("yolov8n.pt")` call | 1–2 hrs to fine-tune |
| AVPDN | Code yes, **weights not public** (author-request only) | Not viable in-window |
| ECC-PolypDet | Code yes, weights on Baidu Drive (access friction) | Not viable in-window |

### Tracking

ByteTrack and BoT-SORT are both built into the `ultralytics` package's tracker configs (`bytetrack.yaml`, `botsort.yaml`), with documented tunable parameters (`track_buffer` default 30 frames, `match_thresh` default 0.8, `new_track_thresh` default 0.25). This is the single most "free" piece of sophistication available to you — confirmed, no caveats.

---

## Technical Opportunities (Quick Wins, Verified Feasible)

1. **Mask-to-box conversion script** (Kvasir-SEG/CVC-ClinicDB masks → YOLO `.txt` format) via `cv2.findContours` + `cv2.boundingRect` — standard, fast, well-trodden path. Whoever owns data prep should do this first, before model training starts.
2. **Albumentations pipeline** simulating motion blur, occlusion (CoarseDropout for fecal matter/bubbles), and glare — trains artifact robustness into the detector without touching the architecture.
3. **Persistence-logic tracking wrapper** on top of `model.track(persist=True)` — hold the last known box for N frames (~150–200ms) when a track drops, so the display doesn't flicker. This is your actual "innovation" story for judges, and it's real, buildable, and honestly described (it's engineering, not a new algorithm — say that plainly in your pitch rather than overselling it).
4. **Custom metrics** (temporal-consistency-style scoring, artifact-false-positive rate on known-negative sequences) — valuable because they let you evaluate on **LDPolypVideo** (which you can actually access) instead of the gated CVC-ClinicVideoDB.

---

## Recommended Reading (verified real, not hallucinated)

1. **"AVPDN: Learning Motion-Robust and Scale-Adaptive Representations for Polyp Detection in Dynamic Colonoscopy Frames"** — Chen & Lu; on arXiv (2508.03458) and Scientific Reports. Read for the artifact taxonomy (motion blur, specular reflection, scale variance) to inform your augmentation choices — **do not attempt to reimplement the architecture.**
2. **"Real-Time Polyp Detection, Localization and Segmentation in Colonoscopy Using Deep Learning"** (Jha et al., 2021, PMC7968127) — solid baseline benchmarking of YOLOv3/v4 vs Faster R-CNN vs RetinaNet vs EfficientDet on Kvasir-SEG; useful for sanity-checking your own numbers.
3. **LDPolypVideo paper** (Ma et al., MICCAI 2021) — read this instead of chasing CVC-ClinicVideoDB access; it's your actual video dataset and this paper documents its structure and known failure modes (SOTA detectors lose 26% recall, 15% precision on it vs static benchmarks — set your expectations accordingly).
4. **Ultralytics Track mode docs** (docs.ultralytics.com/modes/track) — not academic, but this is literally your implementation reference for the tracking layer; more useful in-hackathon than any paper on this list.
5. **Kvasir-SEG dataset paper** (Jha et al., 2020) and **CVC-ClinicDB paper** (Bernal et al., 2015) — for licensing terms and clinical annotation context you'll want for your presentation.

---

## 36-Hour Reality Check

**Fixed critical-path risk (fix this first):** Do not put CVC-ClinicVideoDB acquisition on your Day-1 plan. Email the GIANA organizers on Day 0 if you want to try, but plan your actual pipeline around **Kvasir-SEG + CVC-ClinicDB for training** and **LDPolypVideo for video/temporal evaluation**, both of which you can have downloaded within the first hour.

**Revised critical path:**
1. **Hours 0–2:** Download Kvasir-SEG + CVC-ClinicDB (static, fast). In parallel, start downloading LDPolypVideo (larger — kick it off early since it's your video eval set).
2. **Hours 1–3:** Mask-to-box conversion script; set up Colab + `pip install ultralytics`.
3. **Hours 3–10:** Fine-tune YOLOv8 (start with `yolov8s` or `yolov8m` — nano is fast but weaker; medium is a better accuracy/speed tradeoff on a T4) with Albumentations augmentation baked into the training config. Expect 2–4 hrs of actual GPU training time on a free T4 for ~100 epochs on the combined ~1,600-image set — start this by hour 10 at the latest so you have buffer.
4. **Hours 10–20:** Build the tracking + persistence-logic wrapper; run inference on LDPolypVideo clips; iterate.
5. **Hours 15–30:** Custom metric scripts (temporal consistency, artifact false-positive rate); demo UI (Streamlit/Gradio) showing flickering baseline vs. your stabilized output side-by-side — this is a strong, easy-to-understand demo for judges.
6. **Hours 30–36:** Buffer, pitch deck, rehearsal.

**Explicit scope cuts (confirmed sound, not just asserted):**
- Cut the R-CNN refinement stage entirely — confirmed not viable given latency stacking and lack of plug-and-play temporal ROI modules.
- Cut AVPDN integration — confirmed not viable, no public weights, GPU requirement exceeds free Colab.
- Cut CVC-ClinicVideoDB as a dependency — confirmed access-gated, replace with LDPolypVideo.
- Keep YOLOv8 + native ByteTrack + Albumentations + custom persistence wrapper + custom metrics — every piece of this is confirmed real, documented, and installable with `pip`.

**Team allocation suggestion (3 people):**
- **ML person:** data prep script, YOLO training, tracking + persistence wrapper.
- **Biomedical person:** dataset curation/labeling QA, custom metric definitions grounded in clinical relevance (this is where domain knowledge earns you real credibility with judges), evaluation runs.
- **Generalist:** demo UI, side-by-side comparison video, pitch deck — the flicker-vs-stable comparison is your strongest visual asset, build it early enough to iterate.

---

*Sources checked directly for this report include: Ultralytics official docs and GitHub, the AVPDN GitHub repo itself, GIANA/CVC-Colon official dataset pages, the LDPolypVideo GitHub repo, and multiple independent 2024–2025 arXiv papers benchmarking YOLO variants on Kvasir-SEG. Where a claim could not be verified against a primary source, it was either flagged or omitted rather than repeated.*
