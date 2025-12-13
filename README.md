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
  --np  2
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

### 필요한 데이터

테스트를 위해서는 **다음 파일들이 필요**합니다:

1. **테스트 CSV 파일** (`data/test.csv`):
   - 각 행마다 `path`(바이너리 경로), `metadata_path`(메타데이터 경로), `target`(0/1), `class`(Goodware/Malware) 정보 포함
   
2. **바이너리 파일** (`data/binary/test/*.exe`):
   - 실제 실행 파일들

3. **메타데이터 파일** (`data/metadata/test/*.exe.meta`):
   - 전처리 단계(세션 2)에서 생성된 메타데이터:
     - `insn_addr`: 명령어 주소 범위
     - `exe_section`: 실행 가능한 섹션 범위
     - `header_size`: PE 헤더 크기
   
4. **학습된 체크포인트** (`outputs/models/checkpoint/*.ckpt`):
   - 세션 3에서 생성된 모델 가중치 파일

### 테스트 과정

1. **체크포인트 로드**: 학습된 모델의 가중치와 설정 불러오기
2. **데이터셋 준비**: CSV에서 파일 경로 읽기 → 바이너리 + 메타데이터 로드
3. **Transform 적용**: 
   - PE 헤더 처리 (제거/제로화)
   - 명령어가 아닌 부분 마스킹
   - 텐서 변환
4. **추론 (Inference)**: 각 배치마다 모델에 입력하여 예측
5. **메트릭 계산**: 정확도, 정밀도, 재현율, F1, FPR, FNR 등

### 실행 명령

```bash
python3 src/evaluate_test.py \
  --checkpoint outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt
```

### 출력 결과

실행 후 다음 파일들이 생성됩니다:

1. **예측 결과 CSV** (`{checkpoint_name}_test_predictions.csv`):
   - 각 파일의 실제 라벨, 예측 라벨, 확률값

2. **평가 요약** (`{checkpoint_name}_test_results.txt`):
   - 정확도, 정밀도, 재현율, F1 점수
   - 혼동 행렬
   - FPR (False Positive Rate), FNR (False Negative Rate)

### 추가 옵션

```bash
# 배치 크기 지정
python3 src/evaluate_test.py --checkpoint [path] --batch-size 8

# 결과 저장 디렉토리 지정
python3 src/evaluate_test.py --checkpoint [path] --output-dir outputs/models

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

결정 임계값(Decision Threshold)을 조정하여 목표 오탐율(Target FPR)을 달성합니다.

### 전제 조건

**세션 5 (예측 및 샘플링)가 먼저 완료되어야 합니다!**
- 세션 5에서 `repeat_forward_exp.py`를 실행하여 생성된 확률 데이터(`repeat_probs`)가 필요합니다
- 샘플링 결과는 `outputs/repeat-forward/` 디렉토리에 저장됩니다

### FPR 보정 과정

1. **샘플링 확률 데이터 로드**:
   - 세션 5에서 생성된 `{repeat_name}-{partition}_{num_partitions}.ckpt` 파일들
   - 각 파일에는 `repeat_probs`(반복 예측 확률)와 `metadata`(라벨 정보) 포함

2. **FP 곡선 계산**:
   - 다양한 임계값(threshold)에 대해 FPR 계산
   - 임계값 범위: 0.0 ~ 1.0
   - 각 임계값마다 Goodware(양성) 샘플의 오탐율 측정

3. **최적 임계값 찾기**:
   - 목표 FPR (기본값: 1%) 이하를 만족하는 최소 임계값 선택
   - 예: FPR ≤ 0.01을 만족하는 가장 낮은 threshold

4. **체크포인트 업데이트**:
   - 원본 체크포인트 파일에 다음 정보 추가:
     - `fp_curve`: (임계값, FPR) 곡선 데이터
     - `certified_threshold`: 목표 FPR을 만족하는 임계값
     - `target_fpr`: 설정한 목표 FPR 값

### 실행 명령

```bash
python3 src/fp_curve-repeat_forward.py \
  --path outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt \
  --repeat-conf configs/repeat-forward-exp/malconv-insn_deletion_99.5-header-50.yaml \
  --num-partitions 10 \
  --target-fpr 0.01
```

### 체크포인트 변경사항

**보정 전** (`.ckpt` 파일):
```python
{
  'state_dict': ...,  # 모델 가중치
  'epoch': 10,
  'conf': {...}
}
```

**보정 후** (동일한 `.ckpt` 파일에 추가):
```python
{
  'state_dict': ...,
  'epoch': 10,
  'conf': {...},
  'fp_curve': (thresholds, fpr_values),      # FPR 곡선 데이터
  'certified_threshold': 0.542,              # 선택된 임계값
  'target_fpr': 0.01                         # 목표 FPR (1%)
}
```

### 출력 예시

```
Found threshold for 1.0% FPR: 0.542000 (Actual FPR: 0.009500)
Checkpoint saved at outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt
```

> **참고**: 체크포인트 파일이 **원본 그대로 업데이트**되므로 백업을 권장합니다.

---

## 📜 세션 7: 인증 (Certification)

최종적으로 인증 반경(Certified Radius)을 계산합니다.
  
```bash
python3 src/certify_exp-repeat_forward.py \
  --repeat-conf configs/repeat-forward-exp/sample_config.yaml \
  --certify-conf configs/certify-exp/sample_config.yaml
```




## TEST 데이터 평가 파이프라인 (공격기법별 평가)

학습된 모델을 다양한 공격기법(ExtendDOS, Header, Kreuk, Padding, Slack)으로 변조된 악성코드에 대해 평가합니다.

### 필요한 디렉토리 구조

```plaintext
TEST/
├── ExtendDOS/
│   └── binary/          # ExtendDOS 변조된 실행 파일들
├── Header/
│   └── binary/          # Header 변조된 실행 파일들
├── Kreuk/
│   └── binary/          # Kreuk 변조된 실행 파일들
├── Padding/
│   └── binary/          # Padding 변조된 실행 파일들
└── Slack/
    └── binary/          # Slack 변조된 실행 파일들
```

### 실행 명령 (Docker 컨테이너 내부)

아래 스크립트는 모든 공격기법에 대해 전처리 → 샘플링을 순차적으로 실행합니다:

```bash
bash /app/src/run_test_preprocess.sh
python3 src/filter_timeout_files.py
bash /app/src/run_all_evaluations.sh outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_123.ckpt 
```