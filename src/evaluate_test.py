#!/usr/bin/env python3
"""
테스트 데이터셋으로 학습된 모델의 성능을 평가하는 스크립트

사용법:
    python3 src/evaluate_test.py --checkpoint outputs/models/checkpoint/malconv-insn_deletion_99.5_sd_42.ckpt

출력:
    - 테스트 정확도, 손실, 정밀도, 재현율, F1 점수
    - 혼동 행렬 (Confusion Matrix)
    - 예측 결과 CSV 파일
"""

import argparse
import csv
import os
from collections import Counter
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader
from torch.types import Device

from torchmalware.certification import CertifiedMalConv
from torchmalware.transforms import (
    Compose,
    MaskNonInstruction,
    RemovePEHeader,
    ToTensor,
    Trim,
    ZeroPEHeader,
)
from torchmalware.transforms.transforms import DropMetadata, ShiftByConstant
from torchmalware.metadata import Metadata
from torchmalware.types import IntBinarySample
from torchmalware.utils import collate_pad, seed_worker, set_seed
from utils import make_dataset


def metadata_to(metadata: Metadata, device: Device = None) -> Metadata:
    """메타데이터를 지정된 디바이스로 이동"""
    for key in metadata.keys():
        if isinstance(metadata[key], torch.Tensor):
            metadata[key] = metadata[key].to(device)
    return metadata


def evaluate_model(
    model: CertifiedMalConv,
    test_loader: DataLoader,
    device: str,
    num_samples: int = 1,
) -> Dict:
    """모델을 테스트 데이터셋으로 평가"""
    model.eval()
    model.reduce = "soft"
    
    all_preds = []
    all_targets = []
    all_probs = []
    total_loss = 0.0
    
    ce_loss = nn.CrossEntropyLoss()
    
    with torch.no_grad():
        for batch_idx, batch in enumerate(test_loader):
            (binaries, metadata), targets = batch
            binaries = binaries.to(device)
            metadata = metadata_to(metadata, device=device)
            targets = targets.to(device)
            
            # Forward pass
            logits = model.forward(
                binaries,
                num_samples=num_samples,
                return_logits=True,
                return_radii=False,
                batch_size=targets.size(0),
                forward_kwargs=dict(metadata=metadata),
            )
            
            # Calculate loss
            loss = ce_loss(logits, targets)
            total_loss += loss.item()
            
            # Get predictions and probabilities
            probs = torch.softmax(logits, dim=1)
            preds = logits.argmax(dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(targets.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
            
            if (batch_idx + 1) % 10 == 0:
                print(f"  Processing batch {batch_idx + 1}/{len(test_loader)}", end='\r', flush=True)
    
    print()  # New line after progress
    
    # Convert to numpy arrays
    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)
    all_probs = np.array(all_probs)
    
    # Calculate metrics
    avg_loss = total_loss / len(test_loader)
    accuracy = accuracy_score(all_targets, all_preds)
    precision = precision_score(all_targets, all_preds, average='binary')
    recall = recall_score(all_targets, all_preds, average='binary')
    f1 = f1_score(all_targets, all_preds, average='binary')
    
    # Confusion matrix
    cm = confusion_matrix(all_targets, all_preds)
    
    results = {
        'loss': avg_loss,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'confusion_matrix': cm,
        'predictions': all_preds,
        'targets': all_targets,
        'probabilities': all_probs,
    }
    
    return results


def save_predictions(predictions, targets, probabilities, file_paths, output_path):
    """예측 결과를 CSV 파일로 저장"""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['file_path', 'true_label', 'predicted_label', 'prob_benign', 'prob_malware'])
        
        for i, file_path in enumerate(file_paths):
            writer.writerow([
                file_path,
                int(targets[i]),
                int(predictions[i]),
                float(probabilities[i][0]),
                float(probabilities[i][1])
            ])
    
    print(f"✓ 예측 결과가 저장되었습니다: {output_path}")


def print_evaluation_results(results: Dict):
    """평가 결과를 출력"""
    print("\n" + "=" * 70)
    print("테스트 데이터셋 평가 결과")
    print("=" * 70)
    print(f"손실 (Loss):              {results['loss']:.6f}")
    print(f"정확도 (Accuracy):         {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)")
    print(f"정밀도 (Precision):        {results['precision']:.4f}")
    print(f"재현율 (Recall):           {results['recall']:.4f}")
    print(f"F1 점수:                   {results['f1']:.4f}")
    print("\n혼동 행렬 (Confusion Matrix):")
    print("-" * 70)
    cm = results['confusion_matrix']
    print(f"                    예측: Benign    예측: Malware")
    print(f"실제: Benign        {cm[0][0]:10d}    {cm[0][1]:10d}")
    print(f"실제: Malware       {cm[1][0]:10d}    {cm[1][1]:10d}")
    print("-" * 70)
    
    # Calculate additional metrics
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
    
    print(f"\nFalse Positive Rate (FPR): {fpr:.4f} ({fpr*100:.2f}%)")
    print(f"False Negative Rate (FNR): {fnr:.4f} ({fnr*100:.2f}%)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='학습된 모델을 테스트 데이터로 평가')
    parser.add_argument(
        '--checkpoint',
        type=str,
        required=True,
        help='평가할 모델 체크포인트 경로 (예: outputs/models/checkpoint/model.ckpt)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='결과를 저장할 디렉토리 (기본값: checkpoint와 같은 위치)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help='배치 크기 (기본값: 체크포인트 설정 사용)'
    )
    parser.add_argument(
        '--num-samples',
        type=int,
        default=1,
        help='평가 시 샘플링 횟수 (기본값: 1)'
    )
    parser.add_argument(
        '--device',
        type=str,
        default=None,
        help='사용할 디바이스 (cuda:0, cpu 등, 기본값: 자동 감지)'
    )
    
    args = parser.parse_args()
    
    # 체크포인트 로드
    print(f"체크포인트 로딩 중: {args.checkpoint}")
    if not os.path.exists(args.checkpoint):
        print(f"❌ 오류: 체크포인트 파일을 찾을 수 없습니다: {args.checkpoint}")
        exit(1)
    
    checkpoint = torch.load(args.checkpoint, map_location='cpu')
    conf = checkpoint['conf']
    
    print(f"✓ 체크포인트 로드 완료 (Epoch {checkpoint['epoch']})")
    print(f"  실험 이름: {conf['exp_name']}")
    
    # 시드 설정
    seed = conf['seed']
    if seed is not None:
        set_seed(seed)
        print(f"  시드: {seed}")
    
    # 디바이스 설정
    if args.device:
        device = args.device
    elif torch.cuda.is_available() and conf.get('use_gpu', True):
        device = 'cuda:0'
    else:
        device = 'cpu'
    print(f"  디바이스: {device}")
    
    # 배치 크기 설정
    batch_size = args.batch_size if args.batch_size else conf['batch_size']
    print(f"  배치 크기: {batch_size}")
    
    # Transform 설정 (train.py와 동일)
    data_size = conf['data_size']
    transform = [
        DropMetadata(["binary_path", "exe_section", "header_size", "__file_hash__"]),
        Trim(length=data_size),
    ]
    
    if conf.get('header') == 'remove':
        transform.append(RemovePEHeader())
    elif conf.get('header') == 'zero':
        transform.append(ZeroPEHeader())
    
    if conf.get('non_instruction_mask') is not None:
        transform.append(MaskNonInstruction(conf['non_instruction_mask']))
    
    transform += [
        ToTensor(dtype=torch.int32),
        ShiftByConstant(1),
    ]
    transform = Compose(transform)
    
    # 테스트 데이터셋 로드
    print("\n테스트 데이터셋 로딩 중...")
    test_data = conf.get('test_data')
    if not test_data:
        print("❌ 오류: 설정 파일에 test_data가 정의되지 않았습니다.")
        exit(1)
    
    test_dataset = make_dataset(test_data, transform)
    test_file_paths = [path for path, cls in test_dataset.samples]
    
    print(f"✓ 테스트 데이터셋 로드 완료")
    print(f"  총 파일 수: {len(test_dataset)}")
    counter = Counter(test_dataset.targets)
    print(f"  악성 파일 (Malware):  {counter.get(1, 0)}")
    print(f"  정상 파일 (Benign):   {counter.get(0, 0)}")
    
    # 데이터 로더 생성
    num_workers = conf.get('num_workers')
    if num_workers is None:
        num_workers = torch.get_num_threads()
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        worker_init_fn=seed_worker,
        collate_fn=collate_pad,
        pin_memory=False,
    )
    
    # 모델 로드
    print("\n모델 로딩 중...")
    from torchmalware.certification import perturbations
    
    # Perturbation 설정
    perturbation = perturbations[conf['perturbation']](
        *conf.get('perturbation_args', []),
        **conf.get('perturbation_kwargs', {})
    )
    
    # Embedding 크기 계산
    embed_num = 256
    embed_num += perturbation.extra_dim()
    if conf.get('non_instruction_mask') is not None:
        embed_num = max(embed_num, conf['non_instruction_mask'] + 1)
    embed_num += 1  # Padding
    
    # 모델 생성
    model = CertifiedMalConv(
        perturbation=perturbation,
        out_size=conf['out_size'],
        channels=conf['channels'],
        window_size=conf['window_size'],
        embed_num=embed_num,
        embed_size=conf['embed_size'],
        scale_grad_by_freq=conf.get('scale_grad_by_freq', False),
        threshold=None,
        certify_threshold=None,
        reduce='soft',
    )
    
    # 체크포인트에서 가중치 로드
    model.load_state_dict(checkpoint['state_dict'])
    model = model.to(device)
    model.eval()
    
    print("✓ 모델 로드 완료")
    
    # 평가 실행
    print("\n평가 시작...")
    results = evaluate_model(
        model=model,
        test_loader=test_loader,
        device=device,
        num_samples=args.num_samples,
    )
    
    # 결과 출력
    print_evaluation_results(results)
    
    # 출력 디렉토리 설정
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.dirname(args.checkpoint)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 예측 결과 저장
    checkpoint_name = os.path.splitext(os.path.basename(args.checkpoint))[0]
    pred_output_path = os.path.join(output_dir, f"{checkpoint_name}_test_predictions.csv")
    
    save_predictions(
        predictions=results['predictions'],
        targets=results['targets'],
        probabilities=results['probabilities'],
        file_paths=test_file_paths,
        output_path=pred_output_path
    )
    
    # 평가 결과 요약 저장
    summary_output_path = os.path.join(output_dir, f"{checkpoint_name}_test_results.txt")
    with open(summary_output_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("테스트 데이터셋 평가 결과\n")
        f.write("=" * 70 + "\n")
        f.write(f"체크포인트: {args.checkpoint}\n")
        f.write(f"Epoch: {checkpoint['epoch']}\n")
        f.write(f"실험 이름: {conf['exp_name']}\n")
        f.write(f"\n손실 (Loss):              {results['loss']:.6f}\n")
        f.write(f"정확도 (Accuracy):         {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)\n")
        f.write(f"정밀도 (Precision):        {results['precision']:.4f}\n")
        f.write(f"재현율 (Recall):           {results['recall']:.4f}\n")
        f.write(f"F1 점수:                   {results['f1']:.4f}\n")
        f.write("\n혼동 행렬 (Confusion Matrix):\n")
        f.write("-" * 70 + "\n")
        cm = results['confusion_matrix']
        f.write(f"                    예측: Benign    예측: Malware\n")
        f.write(f"실제: Benign        {cm[0][0]:10d}    {cm[0][1]:10d}\n")
        f.write(f"실제: Malware       {cm[1][0]:10d}    {cm[1][1]:10d}\n")
        f.write("-" * 70 + "\n")
        
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        f.write(f"\nFalse Positive Rate (FPR): {fpr:.4f} ({fpr*100:.2f}%)\n")
        f.write(f"False Negative Rate (FNR): {fnr:.4f} ({fnr*100:.2f}%)\n")
        f.write("=" * 70 + "\n")
    
    print(f"✓ 평가 결과 요약이 저장되었습니다: {summary_output_path}")
    print("\n평가 완료!")
