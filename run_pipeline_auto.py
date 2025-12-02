#!/usr/bin/env python3
"""
자동으로 시스템 리소스를 감지하고 최적화하여 Docker 컨테이너에서 파이프라인을 실행하는 스크립트
"""

import os
import subprocess
import sys
import multiprocessing
import platform

def get_optimal_resources():
    """시스템 리소스를 감지하고 최적의 할당을 계산 (Windows/Linux 크로스 플랫폼)"""
    # CPU 코어 수
    total_cpus = multiprocessing.cpu_count()
    # 전체 코어의 75% 사용 (시스템 안정성 유지)
    allocated_cpus = max(1, int(total_cpus * 0.75))
    # np (병렬 프로세스 수)는 할당된 CPU의 75%
    np_workers = max(1, int(allocated_cpus * 0.75))
    
    # RAM 감지 (GB 단위) - 크로스 플랫폼
    total_ram_gb = None
    allocated_ram_gb = 8  # 기본값
    
    # 방법 1: psutil 사용 (가장 신뢰할 수 있는 크로스 플랫폼 방법)
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_ram_gb = mem.total / (1024 ** 3)  # bytes to GB
        allocated_ram_gb = max(2, int(total_ram_gb * 0.8))
    except ImportError:
        pass
    
    # 방법 2: Linux - /proc/meminfo
    if total_ram_gb is None and platform.system() == 'Linux':
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
            mem_total_kb = int([line for line in meminfo.split('\n') if 'MemTotal' in line][0].split()[1])
            total_ram_gb = mem_total_kb / (1024 * 1024)
            allocated_ram_gb = max(2, int(total_ram_gb * 0.8))
        except:
            pass
    
    # 방법 3: Windows - wmic 명령
    if total_ram_gb is None and platform.system() == 'Windows':
        try:
            result = subprocess.run(
                ['wmic', 'computersystem', 'get', 'totalphysicalmemory'],
                capture_output=True, text=True, shell=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    total_ram_bytes = int(lines[1].strip())
                    total_ram_gb = total_ram_bytes / (1024 ** 3)
                    allocated_ram_gb = max(2, int(total_ram_gb * 0.8))
        except:
            pass
    
    return {
        'total_cpus': total_cpus,
        'allocated_cpus': allocated_cpus,
        'np_workers': np_workers,
        'total_ram_gb': total_ram_gb if 'total_ram_gb' in locals() else 'Unknown',
        'allocated_ram_gb': allocated_ram_gb
    }

def main():
    # 현재 스크립트의 디렉토리로 이동
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("=" * 80)
    print("🚀 자동 최적화 파이프라인 실행기")
    print("=" * 80)
    
    # 시스템 리소스 감지
    resources = get_optimal_resources()
    
    print(f"\n📊 시스템 리소스 감지:")
    print(f"  운영체제: {platform.system()} {platform.release()}")
    print(f"  전체 CPU 코어: {resources['total_cpus']}")
    print(f"  할당 CPU 코어: {resources['allocated_cpus']} (75%)")
    print(f"  병렬 프로세스(np): {resources['np_workers']}")
    if isinstance(resources['total_ram_gb'], (int, float)):
        print(f"  전체 RAM: {resources['total_ram_gb']:.1f}GB")
    print(f"  할당 RAM: {resources['allocated_ram_gb']}GB (80%)")
    
    # GPU 확인
    gpu_available = False
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            gpu_available = True
            print(f"  GPU: 감지됨 ✓")
        else:
            print(f"  GPU: 없음")
    except FileNotFoundError:
        print(f"  GPU: 없음")
    
    print("\n" + "=" * 80)
    print("🐳 Docker 컨테이너 실행 중...")
    print("=" * 80 + "\n")
    
    # Docker 실행 명령 구성
    deploy_script = os.path.join(script_dir, 'docker', 'deploy.py')
    
    docker_cmd = [
        'python3', deploy_script,
        '--cpus', str(resources['allocated_cpus']),
        '--memory', f"{resources['allocated_ram_gb']}g"
    ]
    
    if gpu_available:
        docker_cmd.extend(['--gpus', 'all'])
    else:
        docker_cmd.extend(['--gpus', 'none'])
    
    # 컨테이너 내에서 실행할 파이프라인 명령
    pipeline_commands = f'''
set -e

echo "========================================"
echo "1/3: 재전처리 시작 (timeout 파일 재시도)"
echo "========================================"
python3 src/preprocess_pe.py --root-dir data/binary --save-dir data/metadata --ext .exe --np {resources['np_workers']}

echo ""
echo "========================================"
echo "2/3: CSV 필터링 (실패 파일 제거)"
echo "========================================"
python3 src/filter_timeout_files.py --csv data/train.csv --csv data/valid.csv --csv data/test.csv --reorganize

echo ""
echo "========================================"
echo "3/3: 학습 시작"
echo "========================================"
python3 src/train.py --config configs/models/malconv-insn_deletion_99.5-header.yaml

echo ""
echo "✅ 전체 파이프라인 완료!"
'''
    
    # 임시 스크립트 파일 생성
    temp_script = os.path.join(script_dir, '.temp_pipeline.sh')
    with open(temp_script, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(pipeline_commands)
    
    # chmod는 Unix 계열에서만 필요
    if platform.system() != 'Windows':
        os.chmod(temp_script, 0o755)
    
    try:
        # Docker 컨테이너 실행
        print(f"Docker 명령: {' '.join(docker_cmd)}")
        print(f"\n컨테이너가 시작되면 다음 명령을 실행하세요:")
        print(f"  bash .temp_pipeline.sh\n")
        
        # 대화형 모드로 Docker 실행
        subprocess.call(docker_cmd)
        
    finally:
        # 임시 파일 정리
        if os.path.exists(temp_script):
            os.remove(temp_script)
            print(f"\n🧹 임시 파일 정리 완료")

if __name__ == "__main__":
    main()
