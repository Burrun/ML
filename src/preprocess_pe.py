# This script processes a dataset of raw PE files and saves the result to a new directory. The
# processed dataset includes a metadata file alongside each PE file, which contains:
#   - the address ranges that correspond to individual instructions, as determined by the Ghidra
#     diassembler;
#   - the address ranges that correspond to executable sections, as determined by the `pefile`
#     Python package; and
#   - the size of the PE header in bytes.
# The first item in this list is used to run the deletion smoothing mechanism at the instruction-
# level. If the smoothing mechanism is run solely at the byte-level, there is no need to run this
# script.

import os
import torch
from torch.utils.data import Subset

from torchmalware.datasets.utils import save_dataset
from torchmalware.datasets import RawPE
from torchmalware.transforms import AddInsnAddrRanges, AddExeSectionRanges, AddHeaderSize, Compose
from torchmalware.types import ByteBinarySample
from torchmalware.transforms.functional import to_bytes

from typing import Tuple
import hashlib

def _has_insn_addr_data(insn_addr) -> bool:
    """Return True when insn_addr tensor actually contains entries."""
    try:
        if hasattr(insn_addr, "_nnz"):
            return insn_addr._nnz() > 0
        return insn_addr.sum() != 0
    except Exception:
        return False


def writer(elem: Tuple[ByteBinarySample, int], path: str) -> None:
    sample, _ = elem
    binary, metadata = sample
    os.makedirs(os.path.dirname(path), exist_ok=True)
    metadata_path = path + ".meta"

    # 원본 파일은 건들지 않고 meta만 생성
    # with open(path, "wb") as f:
    #     f.write(to_bytes(binary))

    # 현재 PE 파일 체크섬 계산
    if hasattr(binary, "numpy"):
        binary_bytes = binary.numpy().tobytes()
    else:
        binary_bytes = binary
    current_hash = hashlib.sha256(binary_bytes).hexdigest()
    # 기존 meta 파일이 있으면 불러보고 비교
    if os.path.exists(metadata_path):
        try:
            old_meta = torch.load(metadata_path)
            old_hash = old_meta.get("__file_hash__", None)
            old_insn_addr = old_meta.get("insn_addr", None)
            # hash 동일하고 insn_addr 유효하면 skip
            if old_hash == current_hash and _has_insn_addr_data(old_insn_addr):
                return
        except:
            pass  # meta 깨짐 → 다시 계산하게 둠
    # metadata에 hash 포함시키기
    metadata["__file_hash__"] = current_hash

    torch.save(metadata, metadata_path)


def get_path(idx: int) -> str:
    if isinstance(dataset, Subset):
        idx = dataset.indices[idx]
        path = dataset.dataset.samples[idx][0]
    else:
        path = dataset.samples[idx][0]
    return os.path.abspath(path).replace(root_dir, save_dir)

pe_prep = Compose([
    AddInsnAddrRanges(),
    AddExeSectionRanges(),
    AddHeaderSize(),
])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root-dir",
        type=str,
        required=True,
        help="root directory for raw dataset (conforming to DatasetFolder structure)",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        required=True,
        help="root directory for processed dataset",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        default=False,
        help="whether to log stdout/stderr to file",
    )
    parser.add_argument(
        "--ext",
        type=str,
        required=False,
        default=None,
        help="comma-separated list of file extensions to read from the raw data directory"
    )
    parser.add_argument(
        "--np",
        type=int,
        required=False,
        default=0,
        help="number of subprocesses to use when reading/saving the data",
    )
    parser.add_argument(
        "--range",
        type=str,
        required=False,
        default=None,
        help="'start,end', index range of data to preprocess",
    )
    args = parser.parse_args()
    args.ext = tuple(ext.strip() for ext in args.ext.split(","))

    root_dir = os.path.abspath(args.root_dir)
    save_dir = os.path.abspath(args.save_dir)
    
    dataset = RawPE(root=root_dir, extensions=args.ext, transform=pe_prep)
    if args.range is not None:
        indices = tuple(range(*[int(i) for i in args.range.split(",")]))
        dataset = Subset(dataset, indices)

    
    def skipper(idx: int, save_path: str) -> bool:
        """메타데이터 파일이 존재하고 유효한 경우에만 skip (timeout된 파일은 재시도)"""
        metadata_path = save_path + ".meta"
        
        # 파일이 없으면 처리 필요
        if not os.path.exists(metadata_path):
            return False
        
        # 파일이 있으면 내용 확인
        try:
            metadata = torch.load(metadata_path)
            
            # insn_addr 체크
            if 'insn_addr' not in metadata:
                print(f"🔄 재시도 (insn_addr 키 없음): {metadata_path}")
                return False
            
            insn_addr = metadata['insn_addr']
            if not _has_insn_addr_data(insn_addr):
                print(f"🔄 재시도 (insn_addr 비어있음/timeout): {metadata_path}")
                return False
            
            # 유효한 메타데이터면 skip
            return True
        
        except Exception as e:
            print(f"🔄 재시도 (메타데이터 로드 실패): {metadata_path} - {e}")
            return False

    # Step 1: 먼저 모든 파일 스캔하여 skip 여부 결정
    print("=" * 50)
    print("📋 Step 1: Skip 검사 중...")
    print("=" * 50)
    
    total_files = len(dataset)
    indices_to_process = []
    skipped_count = 0
    
    for idx in range(total_files):
        save_path = get_path(idx)
        if skipper(idx, save_path):
            skipped_count += 1
        else:
            indices_to_process.append(idx)
        
        if (idx + 1) % 500 == 0:
            print(f"  검사 진행: {idx + 1}/{total_files} (skip: {skipped_count})")
    
    print(f"\n📊 검사 완료:")
    print(f"  - 총 파일: {total_files}")
    print(f"  - Skip: {skipped_count}")
    print(f"  - 처리 필요: {len(indices_to_process)}")
    
    if len(indices_to_process) == 0:
        print("\n✅ 모든 파일이 이미 처리되어 있습니다!")
    else:
        # Step 2: 처리가 필요한 파일만 Subset으로 만들어 처리
        print("\n" + "=" * 50)
        print(f"🔧 Step 2: {len(indices_to_process)}개 파일 처리 중...")
        print("=" * 50)
        
        dataset_to_process = Subset(dataset if not isinstance(dataset, Subset) else dataset.dataset, indices_to_process)
        
        def get_path_subset(idx: int) -> str:
            actual_idx = indices_to_process[idx]
            if isinstance(dataset, Subset):
                actual_idx = dataset.indices[actual_idx]
                path = dataset.dataset.samples[actual_idx][0]
            else:
                path = dataset.samples[actual_idx][0]
            return os.path.abspath(path).replace(root_dir, save_dir)
        
        saved_paths = save_dataset(dataset_to_process, get_path_subset, num_workers=args.np, writer=writer, log=args.log)
        
        print(f"\n✅ 처리 완료: {len(saved_paths)}개 파일")

