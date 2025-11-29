# RS-Del: Robustness Certificates for Sequence Classifiers via Randomized Deletion

[![Badge](https://img.shields.io/badge/NeurIPS-2023-blue)](https://nips.cc/Conferences/2023) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository hosts the implementation of our submission to NeurIPS 2023 titled "RS-Del: Edit Distance Robustness Certificates for Sequence Classifiers via Randomized Deletion".

---

## 📂 Directory Structure

```plaintext
.
├── configs
│   ├── certify-exp                   # Configs for evaluation step
│   ├── models                        # Configs for malware detection models
│   └── repeat-forward-exp            # Configs for sampling step
├── data
│   ├── binaries                      # Executables for training and evaluation
│   └── {test,train,valid}.csv        # CSV files for data partitioning
├── docker                            # Docker deployment files
├── outputs                           # Directory for experimental outputs
├── run_scripts                       # Shell scripts for running experiment steps
└── src                               # Source code directory
    ├── torchmalware                  # Python package with core implementations
    ├── train.py                      # Script for training models
    ├── repeat_forward_exp.py         # Script for sampling perturbed inputs
    ├── fp_curve-repeat_forward.py    # Script for computing FPR curve
    └── certify_exp-repeat_forward.py # Script for computing certified radius
```

---

## 🚀 Getting Started

### 1. **Model Training**

- Train the smoothed model using data augmentation via `src/train.py`.
- Example: See `run_scripts/task1-train.sh`.

```bash
python src/train.py --conf configs/models/sample_config.yaml
```

### 2. **Prediction, Certification & Calibration Sampling**

- Save base model confidence scores via `src/repeat_forward_exp.py`.
- Example: See `run_scripts/task2-repeat_forward.sh`.

```bash
python src/repeat_forward_exp.py --conf configs/repeat-forward-exp/sample_config.yaml
```

### 3. **False-Positive Rate Calibration (Optional)**

- Vary the decision threshold and compute the FPR via `src/fp_curve-repeat_forward.py`.
- Example: See `run_scripts/task3-fp_curve.sh`.

```bash
python src/fp_curve-repeat_forward.py --path model/checkpoint.pth --repeat-conf configs/repeat-forward-exp/sample_config.yaml
```

### 4. **Certification**

- Compute the certified radius via `src/certify_exp-repeat_forward.py`.
- Example: See `run_scripts/task4-certify-repeat_forward.sh`.

```bash
python src/certify_exp-repeat_forward.py --repeat-conf configs/repeat-forward-exp/sample_config.yaml --certify-conf configs/certify-exp/sample_config.yaml
```

---

## 🐳 Docker Deployment

Execute the steps in the provided Docker container.

```bash
git clone $REPO_NAME $DEST
cd $DEST/run_scripts
chmod +x ./run.sh
./run.sh -p $SH_PATH -m $MEM -c $NUM_CORES -g $GPU_ID
```

- For sequential execution of all steps (1-4), use `run_scripts/task-full.sh` (Not recommended due to long running time).

---

## 📊 Reproducing Experiments

For reproducing experiments on your dataset, follow the instructions in [`data/README.md`](data/README.md).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Cite us as

```bibtex
@inproceedings{huang2023rsdel,
  author    = {Huang, Zhuoqun and Marchant, Neil and Lucas, Keane and Bauer, Lujo and Ohrimenko, Olya and Rubinstein, Benjamin I. P.},
  title     = {{RS-Del}: Edit Distance Robustness Certificates for Sequence Classifiers via Randomized Deletion},
  year      = {2023},
  booktitle = {Advances in Neural Information Processing Systems},
  series    = {NeurIPS},
}
```

=========================================================================
#0 make_data_and_csv.py

#1 Docker Build  
  
  cd docker 

 DOCKER_BUILDKIT=1 docker build -t rsdel-malware \
  --build-arg USER=$USER \
  --build-arg UID=$(id -u) \
  --build-arg GID=$(id -g) \
  .

  cd ..

#2 Preprocess PE


 docker run -it --rm \
 -v $(pwd):/workspace \
 -w /workspace \
 -e PYTHONPATH=/workspace/src \
 rsdel-malware \
 python3 src/preprocess_pe.py \
 --root-dir data/binary \
 --save-dir data/metadata \
 --ext .exe \




 #3 Model Training

docker run -it --rm \
  --gpus all \
  -v $(pwd):/app\
  -w /app \
  -e PYTHONPATH=/app/src \
  rsdel-malware \
  python3 src/train.py \
  --config configs/models/malconv-insn_deletion_99.5-header.yaml

=========================================================================
make_data_and_csv.py 실행

# 🚀 세션 1: 컨테이너 시작
cd /docker
python3 deploy.py --gpus 0 --memory 16g --cpus 8

# 이제 컨테이너 안:
# [user@container /app]$ 

# 🔧 세션 2: 전처리

python3 src/preprocess_pe.py \
  --root-dir data/binary \
  --save-dir data/metadata \
  --ext .exe \

# 🎓 세션 3: 학습
python3 src/train.py \
  --config configs/models/malconv-insn_deletion_99.5-header.yaml