#!/usr/bin/env python3
"""
CSV 파일에서 insn_addr이 비어있는 파일(timeout된 파일)을 제거하는 스크립트

사용법:
    # 학습 데이터셋 필터링
    python3 src/filter_timeout_files.py --csv data/train.csv --csv data/valid.csv --csv data/test.csv

    # TEST 폴더 내 특정 공격기법 필터링
    python3 src/filter_timeout_files.py --csv TEST/ExtendDOS/test.csv
    python3 src/filter_timeout_files.py --csv TEST/Header/test.csv
    python3 src/filter_timeout_files.py --csv TEST/Kreuk/test.csv
    python3 src/filter_timeout_files.py --csv TEST/Padding/test.csv
    python3 src/filter_timeout_files.py --csv TEST/Slack/test.csv

    # TEST 폴더 내 모든 공격기법 한번에 필터링
    python3 src/filter_timeout_files.py --csv TEST/ExtendDOS/test.csv --csv TEST/Header/test.csv --csv TEST/Kreuk/test.csv --csv TEST/Padding/test.csv --csv TEST/Slack/test.csv
"""

import argparse
import csv
import os
import torch
import shutil
import random
from pathlib import Path
from typing import List, Dict

def check_metadata_valid(metadata_path: str, root_dir: str = None) -> bool:
    """메타데이터 파일이 유효한지 확인 (insn_addr이 비어있지 않은지)"""
    full_path = metadata_path
    if root_dir:
        full_path = os.path.join(root_dir, metadata_path)
    
    if not os.path.exists(full_path):
        # print(f"  ⚠️  메타데이터 파일 없음: {full_path}")
        return False
    
    try:
        metadata = torch.load(full_path)
        
        # insn_addr 체크
        if 'insn_addr' not in metadata:
            # print(f"  ⚠️  insn_addr 키 없음: {full_path}")
            return False
        
        insn_addr = metadata['insn_addr']
        # sparse tensor의 경우 _nnz()로 0이 아닌 요소 개수 확인
        if hasattr(insn_addr, '_nnz'):
            if insn_addr._nnz() == 0:
                # print(f"  ❌ insn_addr 비어있음 (timeout): {full_path}")
                return False
        elif insn_addr.sum() == 0:
            # print(f"  ❌ insn_addr 비어있음 (timeout): {full_path}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  ⚠️  메타데이터 로드 실패: {full_path} - {e}")
        return False

def move_file(src: str, dest: str):
    """파일 이동 (디렉토리 생성 포함)"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)

def filter_timeout_files(csv_paths: List[str], root_dir: str = None):
    """CSV에서 timeout된 파일 제거 및 새 CSV 저장"""
    
    print(f"\n{'='*80}")
    print("🔍 CSV 필터링 시작 (Timeout 파일 제거)")
    print(f"{'='*80}")
    
    for csv_path in csv_paths:
        if not os.path.exists(csv_path):
            print(f"⚠️  CSV 파일 없음: {csv_path}")
            continue
        
        # CSV 백업 생성
        backup_path = csv_path + ".backup"
        shutil.copy2(csv_path, backup_path)
        print(f"💾 백업 생성: {csv_path} → {backup_path}")
        
        # CSV 읽기
        rows = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        total_count = len(rows)
        print(f"📖 읽은 데이터: {total_count}개")
        
        # 유효성 검사
        valid_rows = []
        
        # root_dir 자동 감지 (지정되지 않은 경우)
        current_root_dir = root_dir
        if current_root_dir is None and len(rows) > 0:
            # 첫 번째 항목으로 테스트
            first_meta = rows[0]['metadata_path']
            if not os.path.exists(first_meta):
                # CSV 파일이 있는 디렉토리를 root로 시도
                csv_dir = os.path.dirname(csv_path)
                if os.path.exists(os.path.join(csv_dir, first_meta)):
                    current_root_dir = csv_dir
                    print(f"ℹ️  Root directory 자동 감지: {current_root_dir}")

        for row in rows:
            if check_metadata_valid(row['metadata_path'], current_root_dir):
                valid_rows.append(row)
        
        removed_count = total_count - len(valid_rows)
        print(f"✅ 유효한 데이터: {len(valid_rows)}개")
        print(f"❌ 제거된 데이터 (Timeout): {removed_count}개")
        
        # 새 CSV 저장
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['path', 'metadata_path', 'target', 'class'])
            writer.writeheader()
            writer.writerows(valid_rows)
        
        print(f"💾 저장 완료: {csv_path}")
        print()
    
    print(f"{'='*80}")
    print("✅ 모든 CSV 필터링 완료!")
    print(f"{'='*80}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CSV에서 insn_addr이 비어있는 파일 제거"
    )
    parser.add_argument(
        "--csv",
        type=str,
        action='append',
        required=True,
        help="입력 CSV 파일 경로 (여러 개 지정 가능)"
    )
    
    parser.add_argument(
        "--root-dir",
        type=str,
        default=None,
        help="메타데이터 파일의 루트 디렉토리 (선택사항)"
    )
    
    args = parser.parse_args()
    
    filter_timeout_files(args.csv, args.root_dir)
