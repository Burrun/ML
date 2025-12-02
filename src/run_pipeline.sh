#!/bin/bash
set -e  # 에러 발생 시 중단

echo "========================================="
echo "1/3: 재전처리 시작 (timeout 파일 재시도)"
echo "========================================="
python3 src/preprocess_pe.py --root-dir data/binary --save-dir data/metadata --ext .exe --np 2

echo ""
echo "========================================="
echo "2/3: CSV 필터링 (실패 파일 제거)"
echo "========================================="
python3 src/filter_timeout_files.py --csv data/train.csv --csv data/valid.csv --csv data/test.csv --reorganize

echo ""
echo "========================================="
echo "3/3: 학습 시작"
echo "========================================="
python3 src/train.py --config configs/models/malconv-insn_deletion_99.5-header.yaml

echo ""
echo "✅ 전체 파이프라인 완료!"
