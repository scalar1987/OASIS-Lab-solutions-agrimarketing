# Project Index: OASIS Lab 유통처방 데이터파이프라인

Generated: 2026-03-09

---

## 📁 프로젝트 구조

```
oasis-market/
├── collect_kamis.py              # [핵심] KAMIS API → InfluxDB 수집기 (작동 중)
├── collect_auction_origin.py     # katOrigin/trades → PostgreSQL (dry-run scaffold)
├── collect_auction_settlement.py # katSale/trades → PostgreSQL + InfluxDB (dry-run)
├── collect_shipment_sequel.py    # shipmentSequel/info → InfluxDB (scaffold)
├── prescriber.py                 # 처방 의사결정 엔진 (InfluxDB → 처방 → Supabase)
├── collect_kamis.yml             # GitHub Actions 스케줄러 (매일 06:00 KST)
├── 001_initial_schema.sql        # Supabase 초기 스키마 (마이그레이션)
├── 002_wholesale_auction_schema.sql # 경매원표/정산/출하량 PostgreSQL 스키마
├── OASIS_유통처방_데이터파이프라인_설계_v1.md  # 기술 설계서 (v1)
├── README.md                     # 프로젝트 개요 및 배포 구성
├── .env                          # 환경변수 (gitignore 필요)
└── md_names.txt                  # KAMIS 시장코드 레퍼런스 (지역코드|시장코드|시장명)
```

---

## 🚀 진입점

| 파일 | 용도 | 실행 방법 |
|------|------|---------|
| `collect_kamis.py` | 일별 가격·거래량 수집 | `python collect_kamis.py --date YYYY-MM-DD` |
| `collect_kamis.py` | 과거 데이터 백필 | `python collect_kamis.py --backfill 365` |
| `collect_auction_origin.py` | 경매원표 수집 | `python collect_auction_origin.py --market 1101` |
| `collect_auction_settlement.py` | 정산정보 수집 | `python collect_auction_settlement.py --market 1101` |
| `prescriber.py` | 처방 엔진 실행 | `python prescriber.py` |

---

## 📦 핵심 모듈

### `collect_kamis.py` — KAMIS 수집기 (작동 중)
- **상태**: 프로덕션 수준
- **API**: perDay (`/B552845/perDay/price`) + katSale (`/B552845/katSale/trades`)
- **작목 (CROPS)**: 배추(211), 고추(243), 양파(245), 마늘(244), 대파(246), 감자(152), 사과(411), 배(412), 포도(414)
- **시장**: perDay 6개 시장 + katSale 26개 시장 (전국 공영도매시장 32개 목표)
- **출력**: InfluxDB `kamis_price` (가격), `kamis_volume` (거래량)
- **핵심 함수**: `fetch_daily_price()`, `fetch_kat_sale_items()`, `extract_kat_sale_price()`, `collect_for_date()`, `write_to_influx()`
- **알려진 갭**: perDay 6개 시장 `volume_kg=0.0` 하드코딩 (katSale 거래량 미수집)

### `prescriber.py` — 처방 엔진
- **상태**: 로직 완성, 외부 모듈 미구현 (db/, analyzer/ 폴더 없음)
- **처방 종류**: SHIP_NOW / SHIP_NOW_URGENT / WAIT / SHIP_WITHIN_WEEK / WAIT_7_10 / MONITOR
- **처방 트리**: 가격분위(HIGH/LOW/MIDDLE) → 저장가능여부 → 반입량 모멘텀
- **임계값**: percentile HIGH≥70, LOW≤30 / momentum 급증≥+15%, 감소≤-8%
- **미구현 의존성**: `db.influx_client`, `db.supabase_client`, `analyzer.seasonal`, `analyzer.momentum`

### `collect_auction_settlement.py` — 정산정보 수집기
- **상태**: InfluxDB write 구현, PostgreSQL dry-run
- **API**: `katSale/trades` (katSale와 동일 엔드포인트, 더 상세한 필드 선택)
- **출력**: InfluxDB `kamis_volume` (source=auction_settlement)
- **미구현**: `write_to_postgres()` → Supabase psycopg2 연결 필요

### `collect_auction_origin.py` — 경매원표 수집기
- **상태**: API fetch 구현, 저장 dry-run
- **API**: `katOrigin/trades`
- **미구현**: `write_to_postgres()` → 가장 상세한 원표 데이터

### `collect_shipment_sequel.py` — 출하량 추이
- **상태**: scaffold (API fetch만, write 미구현)
- **API**: `shipmentSequel/info` (주간 출하량 평균, ww1~ww4 비교)

---

## 🗄️ 데이터베이스 스키마

### InfluxDB Cloud (`oasis-market` bucket)
| measurement | tags | fields | 상태 |
|-------------|------|--------|------|
| `kamis_price` | crop_name, market_code, market_name, grade, se | price_per_kg | 수집 중 |
| `kamis_volume` | crop_name, market_code, market_name, source | volume_kg / volume_qty, volume_amt, avg_price | 수집 중 |

### Supabase / PostgreSQL
| 테이블 | 내용 | 상태 |
|--------|------|------|
| `prescriptions` | 처방 결과 (rx_type, current_price, price_percentile, volume_momentum) | 스키마 완성 |
| `crops` | 작목 마스터 (crop_code, storable, t_base, harvest_gdd) | 데이터 입력 완료 |
| `crop_area_stats` | 재배면적 (KOSIS, 연 1회) | 스키마만 |
| `krei_outlook` | 재배의향면적 (KREI, 월 1회) | 스키마만 |
| `farm_profiles` | 농가 프로필 (sido, sigungu, 알림설정) | 스키마 완성 |
| `farm_crops` | 작목별 등록 (출하처, 수확시점, 저장시설) | 스키마 완성 |
| `auction_origin_trades` | 경매원표 원시 | 스키마만 |
| `auction_settlement_daily` | 정산 일집계 | 스키마만 |
| `shipment_sequel_daily` | 출하량 추이 | 스키마만 |

---

## 🔧 환경변수 (.env)

| 변수 | 상태 | 용도 |
|------|------|------|
| `KAMIS_API_KEY` | 설정 완료 | 공공데이터포털 API 인증 |
| `INFLUXDB_URL` | 설정 완료 | InfluxDB Cloud URL |
| `INFLUXDB_TOKEN` | 설정 완료 | InfluxDB 인증 토큰 |
| `INFLUXDB_ORG` | 설정 완료 | `agrimarketing solutions team` |
| `INFLUXDB_BUCKET` | 설정 완료 | `oasis-market` |
| `SUPABASE_URL` | 설정 완료 | Supabase 프로젝트 URL |
| `SUPABASE_ANON_KEY` | **미설정** | 프론트엔드용 공개 키 |
| `SUPABASE_SERVICE_KEY` | **미설정** | 처방 엔진용 서버 키 |

---

## ⚙️ CI/CD (`collect_kamis.yml`)

- **스케줄**: 매일 UTC 21:00 (KST 06:00)
- **timeout**: 60분
- **Secrets 필요** (GitHub repo Settings > Secrets):
  - `KAMIS_API_KEY`, `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`
- **수동 트리거**: `workflow_dispatch` (date 또는 backfill 파라미터)
- **시장 목록** (auction_origin/settlement): `1101 2100 2200 2300 2401 2501 2601`

---

## 📊 외부 API

| API | 엔드포인트 | 용도 | 날짜 포맷 |
|-----|-----------|------|---------|
| perDay | `/B552845/perDay/price` | 일별 도매가 | YYYYMMDD |
| katSale | `/B552845/katSale/trades` | 정산 집계 (거래량+가격) | YYYY-MM-DD |
| katOrigin | `/B552845/katOrigin/trades` | 경매 원표 | YYYY-MM-DD |
| shipmentSequel | `/B552845/shipmentSequel/info` | 출하량 추이 | YYYYMMDD |

**Base**: `https://apis.data.go.kr` / **인증**: `serviceKey` 파라미터

---

## 🔑 KAMIS 코드 레퍼런스

### 품목류코드(ctgry_cd) + 품목코드(item_cd)
| 작목 | ctgry_cd | item_cd |
|------|---------|---------|
| 배추 | 200 | 211 |
| 고추 | 200 | 243 |
| 양파 | 200 | 245 |
| 마늘 | 200 | 244 |
| 대파 | 200 | 246 |
| 감자 | 100 | 152 |
| 사과 | 400 | 411 |
| 배 | 400 | 412 |
| 포도 | 400 | 414 |

### 주요 시장코드
| 시장명 | perDay(7자리) | katSale whsl_mrkt_cd |
|--------|-------------|---------------------|
| 서울가락 | 0110211 | 1101 |
| 서울강서 | - | 1101 |
| 부산엄궁 | 0210042 | 2100 |
| 대구북부 | 0220021 | 2200 |
| 광주각화 | 0240122 | 2401 |
| 광주서부 | 0240123 | 2401 |
| 대전오정 | 0250113 | 2501 |

---

## 🚧 미완성 / TODO

| 항목 | 파일 | 우선순위 |
|------|------|---------|
| perDay 시장 거래량 수집 | `collect_kamis.py` | 높음 — Codex 작업 중 |
| CROPS 상위 20개 품목으로 확대 | `collect_kamis.py` | 높음 — Codex 작업 중 |
| Supabase 키 설정 | `.env` | 높음 |
| PostgreSQL upsert 구현 | `collect_auction_*.py` | 중간 |
| GitHub Actions secrets 등록 | GitHub repo | 중간 |
| `db/`, `analyzer/` 모듈 구현 | 처방 엔진 의존성 | 중간 |
| `collect_shipment_sequel.py` 구현 | - | 낮음 |
| 과거 데이터 백필 (365일~) | - | Codex 완료 후 실행 |

---

## 📚 문서

| 파일 | 내용 |
|------|------|
| `OASIS_유통처방_데이터파이프라인_설계_v1.md` | 전체 기술 설계서 (API 스펙, 알고리즘, UI/UX, 경쟁 분석, 개인화 모델) |
| `README.md` | 배포 구성, 로컬 실행 가이드 |
| `md_names.txt` | KAMIS 전국 시장코드 레퍼런스 |
