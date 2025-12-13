#!/bin/bash

# 사용법: ./run_all_evaluations.sh [CHECKPOINT_PATH] [DEVICE]
# 예: ./run_all_evaluations.sh outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt cuda:0

CHECKPOINT=$1
DEVICE=${2:-cuda:0}

if [ -z "$CHECKPOINT" ]; then
    echo "사용법: $0 [CHECKPOINT_PATH] [DEVICE]"
    echo "예: $0 outputs/models/checkpoint/model.ckpt cuda:0"
    exit 1
fi

if [ ! -f "$CHECKPOINT" ]; then
    echo "❌ 오류: 체크포인트 파일을 찾을 수 없습니다: $CHECKPOINT"
    exit 1
fi

echo "============================================================"
echo "🛡️  다중 시나리오 모델 평가 시작"
echo "============================================================"
echo "체크포인트: $CHECKPOINT"
echo "디바이스: $DEVICE"
echo ""

# 1. 원본 데이터셋 평가 (data/test.csv)
ORIGIN_CSV="data/test.csv"
ORIGIN_OUT="data/output"

if [ -f "$ORIGIN_CSV" ]; then
    echo "------------------------------------------------------------"
    echo "📊 [1/N] 원본 데이터셋 평가 (Origin)"
    echo "CSV: $ORIGIN_CSV"
    echo "Output: $ORIGIN_OUT"
    echo "------------------------------------------------------------"
    
    python3 src/evaluate_test.py \
        --checkpoint "$CHECKPOINT" \
        --test-csv "$ORIGIN_CSV" \
        --output-dir "$ORIGIN_OUT" \
        --data-dir "data" \
        --device "$DEVICE"
        
    echo ""
else
    echo "⚠️ 경고: 원본 테스트 데이터($ORIGIN_CSV)를 찾을 수 없습니다. 건너뜁니다."
    echo ""
fi

# 2. 공격 기법별 데이터셋 평가 (TEST/*/csv/test.csv)
# TEST 디렉토리 내의 모든 하위 디렉토리를 순회
if [ -d "TEST" ]; then
    for attack_dir in TEST/*; do
        if [ -d "$attack_dir" ]; then
            attack_name=$(basename "$attack_dir")
            attack_csv="$attack_dir/test.csv"
            attack_out="$attack_dir/output"
            
            if [ -f "$attack_csv" ]; then
                echo "------------------------------------------------------------"
                echo "📊 공격 시나리오 평가: $attack_name"
                echo "CSV: $attack_csv"
                echo "Output: $attack_out"
                echo "------------------------------------------------------------"
                
                python3 src/evaluate_test.py \
                    --checkpoint "$CHECKPOINT" \
                    --test-csv "$attack_csv" \
                    --output-dir "$attack_out" \
                    --device "$DEVICE"
                
                echo ""
            else
                echo "ℹ️  $attack_name: 테스트 CSV가 없습니다 ($attack_csv). 건너뜁니다."
            fi
        fi
    done
else
    echo "⚠️ 경고: TEST 디렉토리를 찾을 수 없습니다."
fi

echo "============================================================"
echo "✅ 모든 평가가 완료되었습니다."
echo "============================================================"
