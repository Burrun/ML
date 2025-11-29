import os
import shutil
import random
import csv
from pathlib import Path

# ===== Configuration =====
BASE_DIR = Path(__file__).resolve().parent

RAW_ROOT = BASE_DIR / "malware_dataset"

OUT_ROOT = BASE_DIR / "data"
BINARY_DIR = OUT_ROOT / "binary"
METADATA_ROOT = OUT_ROOT / "metadata"

TRAIN_CSV_PATH = OUT_ROOT / "train.csv"
VALID_CSV_PATH = OUT_ROOT / "valid.csv"
TEST_CSV_PATH = OUT_ROOT / "test.csv"

RANDOM_SEED = 123
TRAIN_RATIO = 0.8
TEST_RATIO = 0.1
VALID_RATIO = 0.1
# =========================


def collect_files():
    """RAW_ROOT 아래의 모든 .exe 경로 수집."""
    if not RAW_ROOT.is_dir():
        raise RuntimeError(f"RAW_ROOT not found: {RAW_ROOT}")

    files = list(RAW_ROOT.rglob("*.exe"))
    if not files:
        raise RuntimeError(f"No .exe files found under {RAW_ROOT}")

    print(f"Total .exe samples found: {len(files)}")
    return files


def safe_copy_or_skip(src: Path, dst_dir: Path) -> str | None:
    """
    src 파일을 dst_dir로 복사하되,
    같은 이름의 파일이 이미 존재하면 skip하고 None 반환.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst = dst_dir / src.name
    if dst.exists():
        # 파일 이름 겹치면 pass
        print(f"[SKIP] {src.name} already exists in {dst_dir}")
        return None

    shutil.copy2(src, dst)
    return dst.name


def main():
    random.seed(RANDOM_SEED)

    # 1. 모든 exe 수집
    samples = collect_files()
    random.shuffle(samples)

    n_total = len(samples)
    n_train = int(n_total * TRAIN_RATIO)
    n_test = int(n_total * TEST_RATIO)
    n_valid = n_total - n_train - n_test

    train_samples = samples[:n_train]
    test_samples = samples[n_train:n_train + n_test]
    valid_samples = samples[n_train + n_test:]

    print(f"Split counts -> Train: {len(train_samples)}, Test: {len(test_samples)}, Valid: {len(valid_samples)}")

    # 2. 디렉토리 생성
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    BINARY_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_ROOT.mkdir(parents=True, exist_ok=True)

    for split in ["train", "valid", "test"]:
        (BINARY_DIR / split).mkdir(parents=True, exist_ok=True)
        (METADATA_ROOT / split).mkdir(parents=True, exist_ok=True)

    # 3. CSV 생성
    header = ["path", "metadata_path", "target", "class"]

    with open(TRAIN_CSV_PATH, "w", newline="") as f_train, \
         open(VALID_CSV_PATH, "w", newline="") as f_valid, \
         open(TEST_CSV_PATH, "w", newline="") as f_test:

        w_train = csv.writer(f_train)
        w_valid = csv.writer(f_valid)
        w_test = csv.writer(f_test)

        w_train.writerow(header)
        w_valid.writerow(header)
        w_test.writerow(header)

        def infer_label(src: Path):
            """
            src가 RAW_ROOT 아래라고 가정하고,
            상대 경로의 첫 폴더 이름으로 Malware / Goodware 판별.
            - 'malware'  -> target=1, class='Malware'
            - 'benign'   -> target=0, class='Goodware'
            그 외는 None 반환해서 스킵.
            """
            try:
                rel = src.relative_to(RAW_ROOT)
            except ValueError:
                # RAW_ROOT 밖이면 무시
                return None

            if len(rel.parts) == 0:
                return None

            top = rel.parts[0].lower()

            if top == "malware":
                return 1, "Malware"
            elif top == "benign":
                return 0, "Goodware"
            else:
                # 필요하면 여기서 다른 폴더명도 매핑 추가 가능
                print(f"[WARN] Unknown label folder '{top}' in path '{rel}', skipping")
                return None

        def write_split(split_samples, split_name, writer):
            bin_dir = BINARY_DIR / split_name

            for src in split_samples:
                # 라벨 추론 (Malware / Goodware)
                label = infer_label(src)
                if label is None:
                    # benign/malware 아닌 경우 스킵
                    continue
                target_val, class_val = label

                fname = safe_copy_or_skip(src, bin_dir)
                if fname is None:
                    # skip된 파일은 CSV에 기록하지 않음
                    continue

                # 경로 (data/ 기준)
                path_val = f"binary/{split_name}/{fname}"
                meta_val = f"metadata/{split_name}/{fname}.meta"

                writer.writerow([
                    path_val,
                    meta_val,
                    target_val,   # 1 or 0
                    class_val     # 'Malware' or 'Goodware'
                ])

        print("Copy + Writing train.csv ...")
        write_split(train_samples, "train", w_train)

        print("Copy + Writing valid.csv ...")
        write_split(valid_samples, "valid", w_valid)

        print("Copy + Writing test.csv ...")
        write_split(test_samples, "test", w_test)

    print("Done.")
    print(f"Binary dirs   : {BINARY_DIR}/(train|valid|test)")
    print(f"Metadata dirs : {METADATA_ROOT}/(train|valid|test)")
    print(f"Train CSV     : {TRAIN_CSV_PATH}")
    print(f"Valid CSV     : {VALID_CSV_PATH}")
    print(f"Test CSV      : {TEST_CSV_PATH}")


if __name__ == "__main__":
    main()
