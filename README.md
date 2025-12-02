# RS-Del: Robustness Certificates for Sequence Classifiers via Randomized Deletion

## 📂 디렉토리 구조 (Directory Structure)

```plaintext
.
├── configs
│   ├── certify-exp                   # 평가 단계 설정
│   ├── models                        # 악성코드 탐지 모델 설정
│   └── repeat-forward-exp            # 샘플링 단계 설정
├── data
│   ├── binaries                      # 학습 및 평가용 실행 파일
│   └── {test,train,valid}.csv        # 데이터 분할 CSV 파일
├── docker                            # Docker 배포 파일
├── outputs                           # 실험 결과 출력 디렉토리
├── run_scripts                       # 실험 단계 실행 쉘 스크립트
└── src                               # 소스 코드 디렉토리
    ├── torchmalware                  # 핵심 구현 파이썬 패키지
    ├── train.py                      # 모델 학습 스크립트
    ├── repeat_forward_exp.py         # 변형된 입력 샘플링 스크립트
    ├── fp_curve-repeat_forward.py    # FPR 곡선 계산 스크립트
    └── certify_exp-repeat_forward.py # 인증 반경 계산 스크립트
```

---

## 🚀 세션 1: 컨테이너 시작 (Container Start)

가장 먼저 Docker 컨테이너를 실행하여 환경을 구축합니다.

```bash
cd docker && python3 deploy.py --gpus 0 --memory 16g 
```

> **참고:** 컨테이너 내부로 진입하면 프롬프트가 `[user@container /app]$` 형태로 변경됩니다.

---

## 🔧 세션 2: 전처리 (Preprocessing)

수집한 실행 파일(.exe)을 학습에 필요한 메타데이터로 변환합니다.
* np는 프로세스 개수를 의미, 0.75cpu코어 수로 설정
```bash
python3 src/preprocess_pe.py \
  --root-dir data/binary \
  --save-dir data/metadata \
  --ext .exe \
  --np 2 
```  

# 전처리 완료 후 timeout된 파일 제거(어쩔 수 없음 ...)
python3 filter_timeout_files.py \
  --csv data/train.csv \
  --csv data/valid.csv \
  --csv data/test.csv

*복원 방법: mv data/train.csv.backup data/train.csv 

## 🎓 세션 3: 학습 (Training)

전처리된 데이터를 사용하여 모델 학습을 시작합니다.

```bash
python3 src/train.py \
  --config configs/models/malconv-insn_deletion_99.5-header.yaml
```

---

## 🔮 세션 4: 예측 및 샘플링 (Prediction & Sampling)

베이스 모델의 신뢰도 점수(Confidence Scores)를 저장하고 인증을 위한 샘플링을 수행합니다.

```bash
python3 src/repeat_forward_exp.py \
  --conf configs/repeat-forward-exp/sample_config.yaml
```

---

## ⚖️ 세션 5: 오탐율 보정 (FPR Calibration) - 선택 사항

결정 임계값(Decision Threshold)을 조정하여 오탐율(FPR)을 계산합니다.

```bash
python3 src/fp_curve-repeat_forward.py \
  --path model/checkpoint.pth \
  --repeat-conf configs/repeat-forward-exp/sample_config.yaml
```

---

## 📜 세션 6: 인증 (Certification)

최종적으로 인증 반경(Certified Radius)을 계산합니다.

```bash
python3 src/certify_exp-repeat_forward.py \
  --repeat-conf configs/repeat-forward-exp/sample_config.yaml \
  --certify-conf configs/certify-exp/sample_config.yaml
```


-------------------------------------------
도커 설치 / git 설치 / 
git clone https://github.com/Burrun/ML.git
pip install psutil
python3 run_pipeline_auto.py
