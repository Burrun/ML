#!/usr/bin/env python3
"""
CSV 파일에서 insn_addr이 비어있는 파일(timeout된 파일)을 제거하고,
데이터셋을 6:2:2 비율로 재분할하여 파일을 이동시키는 스크립트

사용법:
    python3 src/filter_timeout_files.py --csv data/train.csv --csv data/valid.csv --csv data/test.csv --reorganize
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
    if root_dir:
        metadata_path = os.path.join(root_dir, metadata_path)
    
    if not os.path.exists(metadata_path):
        # print(f"  ⚠️  메타데이터 파일 없음: {metadata_path}")
        return False
    
    try:
        metadata = torch.load(metadata_path)
        
        # insn_addr 체크
        if 'insn_addr' not in metadata:
            # print(f"  ⚠️  insn_addr 키 없음: {metadata_path}")
            return False
        
        insn_addr = metadata['insn_addr']
        # sparse tensor의 경우 _nnz()로 0이 아닌 요소 개수 확인
        if hasattr(insn_addr, '_nnz'):
            if insn_addr._nnz() == 0:
                # print(f"  ❌ insn_addr 비어있음 (timeout): {metadata_path}")
                return False
        elif insn_addr.sum() == 0:
            # print(f"  ❌ insn_addr 비어있음 (timeout): {metadata_path}")
            return False
        
        return True
    
    except Exception as e:
        print(f"  ⚠️  메타데이터 로드 실패: {metadata_path} - {e}")
        return False

def move_file(src: str, dest: str):
    """파일 이동 (디렉토리 생성 포함)"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.move(src, dest)

def reorganize_dataset(csv_paths: List[str], root_dir: str = None):
    """데이터셋 재구성: 필터링 -> 셔플 -> 분할 -> 이동"""
    
    print(f"\n{'='*80}")
    print("🔄 데이터셋 재구성 시작 (필터링 + 셔플 + 분할 + 이동)")
    print(f"{'='*80}")

    all_rows = []
    
    # 1. 모든 CSV 읽기
    print("📖 CSV 파일 읽는 중...")
    for csv_path in csv_paths:
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_rows.append(row)
    
    print(f"  총 읽은 데이터: {len(all_rows)}개")

    # 2. 유효성 검사 (필터링)
    print("🔍 유효성 검사 중 (Timeout 파일 제거)...")
    valid_rows = []
    for row in all_rows:
        if check_metadata_valid(row['metadata_path'], root_dir):
            valid_rows.append(row)
    
    print(f"  유효한 데이터: {len(valid_rows)}개 (제거됨: {len(all_rows) - len(valid_rows)}개)")

    # 3. 셔플
    print("🔀 데이터 셔플 중...")
    random.seed(42) # 재현성을 위해 시드 고정
    random.shuffle(valid_rows)

    # 4. 분할 (6:2:2)
    total = len(valid_rows)
    n_train = int(total * 0.6)
    n_valid = int(total * 0.2)
    n_test = total - n_train - n_valid

    splits = {
        'train': valid_rows[:n_train],
        'valid': valid_rows[n_train:n_train+n_valid],
        'test': valid_rows[n_train+n_valid:]
    }

    print(f"📊 분할 결과: Train({len(splits['train'])}) / Valid({len(splits['valid'])}) / Test({len(splits['test'])})")

    # 5. 파일 이동 및 CSV 저장
    print("🚚 파일 이동 및 CSV 저장 중...")
    
    # 기본 경로 설정 (data/binary, data/metadata)
    base_binary_dir = "data/binary"
    base_metadata_dir = "data/metadata"

    for split_name, rows in splits.items():
        new_csv_path = f"data/{split_name}.csv"
        new_rows = []
        
        print(f"  Processing {split_name} set...")
        
        for row in rows:
            old_binary_path = row['path']
            old_metadata_path = row['metadata_path']
            filename = os.path.basename(old_binary_path)
            
            # 새 경로 설정
            new_binary_path = os.path.join(base_binary_dir, split_name, filename)
            new_metadata_path = os.path.join(base_metadata_dir, split_name, filename + ".meta")
            
            # 파일 이동 (실제 경로가 다를 경우에만)
            # 주의: 상대 경로 처리를 위해 절대 경로로 변환하여 비교하거나, 단순히 이동 시도
            try:
                if os.path.abspath(old_binary_path) != os.path.abspath(new_binary_path):
                    if os.path.exists(old_binary_path):
                        move_file(old_binary_path, new_binary_path)
                
                if os.path.abspath(old_metadata_path) != os.path.abspath(new_metadata_path):
                    if os.path.exists(old_metadata_path):
                        move_file(old_metadata_path, new_metadata_path)
            except Exception as e:
                print(f"    ❌ 파일 이동 실패: {filename} - {e}")
                continue # 이동 실패 시 해당 항목 제외? 아니면 경고만? 일단 진행

            # CSV용 경로 업데이트 (상대 경로 유지)
            new_row = row.copy()
            new_row['path'] = new_binary_path
            new_row['metadata_path'] = new_metadata_path
            new_rows.append(new_row)

        # CSV 저장
        if new_rows:
            with open(new_csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['path', 'metadata_path', 'target', 'class'])
                writer.writeheader()
                writer.writerows(new_rows)
            print(f"    ✅ {new_csv_path} 저장 완료")

    print(f"\n{'='*80}")
    print("✅ 모든 작업 완료!")
    print(f"{'='*80}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CSV에서 insn_addr이 비어있는 파일 제거 및 데이터셋 재구성"
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
        help="메타데이터 파일의 루트 디렉토리"
    )
    parser.add_argument(
        "--reorganize",
        action='store_true',
        help="데이터셋 재구성 (셔플, 분할, 파일 이동) 수행"
    )
    
    args = parser.parse_args()
    
    if args.reorganize:
        reorganize_dataset(args.csv, args.root_dir)
    else:
        print("⚠️ --reorganize 옵션을 사용해주세요.")

