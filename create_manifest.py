#!/usr/bin/env python3
"""
AI Hub 식물 병해 데이터셋 Manifest 생성 스크립트
"""

import os
import json
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 데이터셋 경로 설정
DATASET_PATH = Path(r"C:\오아시스랩\오아시스vision\ai hub_images")
OUTPUT_DIR = Path(r"C:\오아시스랩\오아시스Vision")

def parse_filename(filepath):
    """
    파일명에서 메타데이터 추출
    예: 512706_20211018_5_0_0_3_2_12_0_804.jpg
    """
    filename = filepath.stem
    parts = filename.split('_')

    metadata = {
        'filename': filepath.name,
        'file_id': parts[0] if len(parts) > 0 else None,
        'date': parts[1] if len(parts) > 1 else None,
    }
    return metadata

def create_manifest():
    """메인 manifest 생성 함수"""

    if not DATASET_PATH.exists():
        print(f"❌ 경로를 찾을 수 없습니다: {DATASET_PATH}")
        print("경로를 확인하고 스크립트 상단의 DATASET_PATH를 수정해주세요.")
        return

    print(f"📂 데이터셋 경로: {DATASET_PATH}")
    print("🔍 파일 스캔 중...")

    # 데이터 수집
    dataset = []
    stats = defaultdict(int)
    category_counts = defaultdict(int)

    # 각 카테고리 폴더 순회
    for category_dir in DATASET_PATH.iterdir():
        if not category_dir.is_dir():
            continue

        category_name = category_dir.name
        print(f"  ├─ {category_name}")

        # 하위 폴더 순회 (작물명/병해-정상)
        for subdir in category_dir.rglob("*"):
            if not subdir.is_dir():
                continue

            # 이미지 파일 찾기
            for img_file in subdir.glob("*.jpg"):
                # 상대 경로 계산
                rel_path = img_file.relative_to(DATASET_PATH)

                # 레이블 추출 (폴더 구조에서)
                path_parts = rel_path.parts

                # VS4_고추_정상 -> 고추, 정상
                category_parts = category_name.split('_')
                crop = category_parts[1] if len(category_parts) > 1 else "Unknown"
                status = category_parts[2] if len(category_parts) > 2 else "Unknown"

                # 메타데이터 파싱
                metadata = parse_filename(img_file)

                # 데이터 추가
                data_entry = {
                    'file_path': str(rel_path).replace('\\', '/'),
                    'absolute_path': str(img_file),
                    'category': category_name,
                    'crop': crop,
                    'status': status,
                    'label': f"{crop}_{status}",
                    **metadata
                }

                dataset.append(data_entry)

                # 통계
                stats['total_images'] += 1
                category_counts[category_name] += 1
                category_counts[f"{crop}_{status}"] += 1

    print(f"\n✅ 총 {stats['total_images']:,}개 이미지 발견")

    # 1. CSV Manifest 생성
    csv_path = OUTPUT_DIR / "manifest.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        if dataset:
            writer = csv.DictWriter(f, fieldnames=dataset[0].keys())
            writer.writeheader()
            writer.writerows(dataset)
    print(f"📄 CSV Manifest 생성: {csv_path}")

    # 2. JSON Manifest 생성
    json_manifest = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'dataset_name': 'AI Hub 식물 병해 통합 데이터',
            'total_images': stats['total_images'],
            'categories': len(category_counts),
        },
        'statistics': dict(category_counts),
        'data': dataset
    }

    json_path = OUTPUT_DIR / "manifest.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_manifest, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON Manifest 생성: {json_path}")

    # 3. 통계 리포트 생성
    stats_path = OUTPUT_DIR / "dataset_statistics.txt"
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("AI Hub 식물 병해 데이터셋 통계\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"총 이미지 수: {stats['total_images']:,}개\n\n")
        f.write("카테고리별 분포:\n")
        f.write("-" * 60 + "\n")
        for category, count in sorted(category_counts.items()):
            percentage = (count / stats['total_images'] * 100) if stats['total_images'] > 0 else 0
            f.write(f"{category:30s}: {count:>8,}개 ({percentage:>5.2f}%)\n")

    print(f"📊 통계 리포트 생성: {stats_path}")

    # 4. 간단한 요약 출력
    print("\n" + "=" * 60)
    print("📊 데이터셋 요약")
    print("=" * 60)
    for category, count in sorted(category_counts.items()):
        if category.startswith("VS"):
            print(f"  {category}: {count:,}개")
    print("=" * 60)
    print("\n✨ Manifest 생성 완료!")

if __name__ == "__main__":
    create_manifest()
