# CHAKRA — Medical AI Monorepo

Consolidated monorepo for ChakraModel medical AI systems.

## Projects
| Project | Path | Status |
|---|---|---|
| Colonoscopy Polyp Detection | `ml/tasks/colonoscopy-polyp-detection/` | Active |
| Fetal CHD Detection | `ml/tasks/fetal-chd/` | Early Dev |
| LeakBench | `ml/evaluation/benchmarks/leakbench/` | Active |

## Structure
```
D:\CHAKRA\
  ml/
    tasks/              <- per-model source code + tests + archive
    evaluation/         <- benchmarks (leakbench)
    experiments/        <- notebooks, training runs
    registry/           <- model weights
  data/
    stages/             <- 00-raw ... 06-curated-releases
  regulatory/           <- FDA, EU-MDR, CDSCO
  security/             <- threat models, credentials policies
  infra/                <- dev/staging/prod environments
  docs/                 <- architecture, ADRs, API docs
```

## Setup
```bash
# Clone
git clone https://github.com/Gokzz-glitch/chakramodel.git
cd chakramodel

# Install (polyp detection)
cd ml/tasks/colonoscopy-polyp-detection
pip install -r requirements.txt
```

## Drives
- **Primary**: `D:\CHAKRA` (Seagate HDD, 3.64 TB)
- **Legacy source**: `D:\donot delete gokul\chakramodel` (preserved, not deleted)
