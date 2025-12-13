#!/bin/bash
set -e

# Docker 컨테이너 내부에서 실행 (/app 디렉토리 기준)
# 각 공격기법에 대해 전처리 실행
# export GHIDRA_ANALYSIS_TIMEOUT=120

cd /app

echo ""
echo "========================================"
echo "🔧 data/ 폴더 전처리 시작..."
echo "========================================"

# for split in train valid test; do
#     echo "----------------------------------------"
#     echo "📁 data/binary/$split 전처리 중..."
#     echo "----------------------------------------"
    
#     if [ ! -d "/app/data/binary/$split" ]; then
#         echo "⚠️  /app/data/binary/$split 디렉토리가 없습니다. 건너뜁니다."
#         continue
#     fi
    
#     mkdir -p /app/data/metadata/$split
    
#     python3 /app/src/preprocess_pe.py \
#         --root-dir /app/data/binary/$split \
#         --save-dir /app/data/metadata/$split \
#         --ext .exe \
#         --np 2 
        
#     echo "✅ data/$split 완료"
#     echo ""
# done


for method in ExtendDOS Header Kreuk Padding Slack; do
    echo "========================================"
    echo "🔧 $method 전처리 중..."
    echo "========================================"
    
    # binary 폴더가 존재하는지 확인
    if [ ! -d "/app/TEST/$method/binary" ]; then
        echo "⚠️  /app/TEST/$method/binary 디렉토리가 없습니다. 건너뜁니다."
        continue
    fi
    
    # metadata 폴더 생성
    mkdir -p /app/TEST/$method/metadata
    
    # preprocess_pe.py 실행
    # --root-dir: 입력 바이너리 폴더
    # --save-dir: 출력 메타데이터 폴더
    # --ext: 처리할 확장자
    # --np: 병렬 프로세스 수 
    python3 /app/src/preprocess_pe.py \
        --root-dir /app/TEST/$method/binary \
        --save-dir /app/TEST/$method/metadata \
        --ext .exe  
        
    echo "✅ $method 완료"
    echo ""
done



echo "🎉 모든 전처리 작업이 완료되었습니다!"