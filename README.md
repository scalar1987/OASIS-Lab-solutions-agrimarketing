# OASIS Market — 유통 처방 엔진

> OASIS Lab의 농산물 유통 타이밍 처방 시스템.
> aT KAMIS 공공 데이터를 기반으로 도매가 계절성 분석 + 반입량 모멘텀을 결합해
> 소농에게 "이번 주 출하 vs 대기" 처방을 제공한다.

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  [1] 데이터 수집                                              │
│                                                              │
│  GitHub Actions (cron: 매일 06:00 KST)                       │
│    └─ collect_kamis.py                                       │
│         ├─ aT KAMIS perDay API ?????? (????????? ?????????, kg??????)
│         └─ InfluxDB Cloud 적재                               │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  [2] 처방 엔진                                               │
│                                                              │
│  Railway (상시 실행 FastAPI 서버)                             │
│    └─ APScheduler (매일 07:00 KST)                           │
│         ├─ InfluxDB에서 가격·반입량 시계열 읽기               │
│         ├─ 계절성 분석 (STL) + 반입량 모멘텀 계산             │
│         ├─ 처방 의사결정 트리 실행                            │
│         └─ Supabase에 처방 결과 저장                         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  [3] 데이터 저장                                             │
│                                                              │
│  InfluxDB Cloud (시계열 DB)                                  │
│    ├─ measurement: kamis_price  (도매가·소매가)              │
│    └─ measurement: kamis_volume (?????????, ?????? ?????????)                     │
│                                                              │
│  Supabase / PostgreSQL (마스터 DB)                           │
│    ├─ table: prescriptions      (처방 결과)                  │
│    ├─ table: crop_area_stats    (재배면적 — 통계청)           │
│    └─ table: krei_outlook       (재배의향면적 — KREI)         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  [4] 프론트엔드                                              │
│                                                              │
│  Vercel (Next.js)                                            │
│    ├─ Supabase JS SDK → 처방 결과 실시간 구독                │
│    └─ InfluxDB API   → 가격·반입량 차트 데이터               │
└─────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
oasis-market/
│
├── .github/
│   └── workflows/
│       └── collect_kamis.yml       # GitHub Actions: 매일 KAMIS 수집
│
├── collector/                      # [1] 데이터 수집
│   ├── collect_kamis.py            # KAMIS API → InfluxDB 적재
│   ├── collect_kosis.py            # 통계청 재배면적 → Supabase 적재 (연 1회)
│   └── requirements.txt
│
├── engine/                         # [2] 처방 엔진 (Railway 배포)
│   ├── main.py                     # FastAPI 진입점
│   ├── scheduler.py                # APScheduler 설정
│   ├── prescriber.py               # 처방 의사결정 로직
│   ├── analyzer/
│   │   ├── seasonal.py             # STL 계절성 분석
│   │   ├── momentum.py             # 반입량 모멘텀
│   │   └── gdd.py                  # GDD 수확시점 추정
│   ├── db/
│   │   ├── influx_client.py        # InfluxDB 읽기
│   │   └── supabase_client.py      # Supabase 쓰기
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                       # [4] Next.js 프론트엔드 (Vercel 배포)
│   ├── app/
│   │   ├── page.tsx                # 메인 대시보드
│   │   └── api/
│   │       └── chart-data/
│   │           └── route.ts        # InfluxDB → 차트 데이터 API
│   ├── components/
│   │   ├── PrescriptionCard.tsx    # 처방 카드
│   │   ├── PriceChart.tsx          # 가격 차트
│   │   └── VolumeChart.tsx         # 반입량 차트
│   └── package.json
│
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql  # Supabase 테이블 정의
│
├── .env.example                    # 환경변수 템플릿
└── README.md
```

---

## 환경변수

```bash
# .env.example

# aT KAMIS
KAMIS_API_KEY=your_key_here

# InfluxDB Cloud
INFLUXDB_URL=https://us-east-1-1.aws.cloud2.influxdata.com
INFLUXDB_TOKEN=your_token_here
INFLUXDB_ORG=your_org_here
INFLUXDB_BUCKET=oasis-market

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_key_here   # 서버용 (비공개)
SUPABASE_ANON_KEY=your_anon_key_here         # 프론트엔드용 (공개 가능)
```

---

## 배포 구성

| 컴포넌트 | 플랫폼 | 무료 티어 한계 | 비고 |
|---------|--------|--------------|------|
| 데이터 수집 | GitHub Actions | 월 2,000분 | 매일 1회 실행 → 월 ~30분 소요 |
| 처방 엔진 | Railway | $5 크레딧/월 | 상시 실행 필요 (서버리스 불가) |
| 시계열 DB | InfluxDB Cloud | 30일 보존, 5GB | 가격 데이터만으론 충분 |
| 마스터 DB | Supabase | 500MB, 50MB 파일 | 처방 결과 적재 충분 |
| 프론트엔드 | Vercel | 무제한 | Next.js 정적/SSR |

---

## 로컬 실행

```bash
# 1. 저장소 클론
git clone https://github.com/your-org/oasis-market.git
cd oasis-market

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 실제 키 입력

# 3. 수집기 실행 (로컬 테스트)
pip install -r requirements.txt
python collect_kamis.py --date 2026-03-09

# 4. 처방 엔진 실행
cd ../engine
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 5. 프론트엔드
cd ../frontend
npm install
npm run dev
```

---

## KAMIS perDay API

- ?????? URL: https://apis.data.go.kr/B552845/perDay/price
- ?????? ????????????: `cond[exmn_ymd::GTE]`, `cond[exmn_ymd::LTE]`, `cond[ctgry_cd::EQ]`, `cond[item_cd::EQ]`
- ?????? ??????: `YYYYMMDD`
- ?????? ??????: ??????/??????/?????? ?????? ?????? ????????? ?????? ?????? ??? (?????? ?????? 7??????)
- ????????? ?????? ????????? ???????????? ????????? ????????? ??????
