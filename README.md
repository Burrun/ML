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
python3 docker/deploy.py --gpus 0 --memory 16g 
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

## 🎓 세션 3: 학습 (Training)

전처리된 데이터를 사용하여 모델 학습을 시작합니다.

```bash
python3 src/train.py \
  --config configs/models/malconv-insn_deletion_99.5-header.yaml
```

* 학습 중 체크포인트는 `outputs/models/checkpoint/` 디렉토리에 자동 저장됩니다
* 체크포인트 형식: `{exp_name}_sd_{seed}.ckpt` 및 `{exp_name}_sd_{seed}-step_{step}.ckpt`

---

## 📊 세션 4: 테스트 데이터 평가 (Test Evaluation)

학습된 모델을 테스트 데이터로 평가하여 최종 성능을 측정합니다.

```bash
python3 src/evaluate_test.py \
  --checkpoint outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt
```

**출력 결과:**
- 정확도 (Accuracy), 정밀도 (Precision), 재현율 (Recall), F1 점수
- 혼동 행렬 (Confusion Matrix)
- False Positive Rate (FPR), False Negative Rate (FNR)
- 예측 결과 CSV 파일 (`_test_predictions.csv`)
- 평가 요약 텍스트 파일 (`_test_results.txt`)

**추가 옵션:**
```bash
# 배치 크기 지정
python3 src/evaluate_test.py --checkpoint [path] --batch-size 8

# 결과 저장 디렉토리 지정
python3 src/evaluate_test.py --checkpoint [path] --output-dir results/

# CPU 사용 강제
python3 src/evaluate_test.py --checkpoint [path] --device cpu
```

---

## 🔮 세션 5: 예측 및 샘플링 (Prediction & Sampling)

베이스 모델의 신뢰도 점수(Confidence Scores)를 저장하고 인증을 위한 샘플링을 수행합니다.

```bash
python3 src/repeat_forward_exp.py \
  --conf configs/repeat-forward-exp/malconv-insn_deletion_99.5-header-50.yaml
```

---

## ⚖️ 세션 6: 오탐율 보정 (FPR Calibration) - 선택 사항

결정 임계값(Decision Threshold)을 조정하여 오탐율(FPR)을 계산합니다.

```bash
python3 src/fp_curve-repeat_forward.py \
  --path outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt \
  --repeat-conf configs/repeat-forward-exp/malconv-insn_deletion_99.5-header-50.yaml
```

---

## 📜 세션 7: 인증 (Certification)

최종적으로 인증 반경(Certified Radius)을 계산합니다.
  
```bash
python3 src/certify_exp-repeat_forward.py \
  --repeat-conf configs/repeat-forward-exp/sample_config.yaml \
  --certify-conf configs/certify-exp/sample_config.yaml
```
