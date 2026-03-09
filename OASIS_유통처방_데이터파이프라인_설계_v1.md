# OASIS Lab — 유통 처방 데이터 파이프라인 기술 설계서

> **문서 목적**: 구현 담당자용 기술 설계 문서. 사업계획서(2부)의 개요 수준에서 다루지 않은 API 엔드포인트, 스키마, 처방 알고리즘 상세를 기록한다.
> **버전**: v1.0 | **작성일**: 2026-03 | **작성**: OASIS Lab CEO

---

## 1. 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                       외부 데이터 수집 레이어                      │
│                                                                  │
│  [고빈도 — 일별/시간별]          [저빈도 — 월별/연별]              │
│  aT KAMIS API (가격·반입량)      통계청 KOSIS API (재배면적)        │
│  기상청 API (기온·강수)          KREI 농업관측월보 (크롤링)          │
│  Sentinel-2 NDVI (격주)         관세청 수출입통계 API (수입량)      │
│                                                                  │
└──────────────┬────────────────────────────┬─────────────────────┘
               │                            │
               ▼                            ▼
        ┌─────────────┐             ┌──────────────┐
        │  InfluxDB   │             │  PostgreSQL  │
        │ (시계열 DB)  │             │ (마스터 DB)  │
        │             │             │              │
        │ • 가격 시계열 │             │ • 재배면적    │
        │ • 반입량     │             │ • 수입량      │
        │ • 기상 데이터 │             │ • 처방 결과   │
        │ • 센서 데이터 │             │ • 농가 정보   │
        │ • NDVI      │             │ • KREI 전망  │
        └──────┬───────┘             └──────┬───────┘
               │                            │
               └──────────────┬─────────────┘
                              ▼
              ┌───────────────────────────────┐
              │   처방 엔진 (FastAPI + Python) │
              │                               │
              │  • GDD 수확시점 추정 모듈       │
              │  • 가격 계절성 분석 모듈        │
              │  • 반입량 모멘텀 모듈           │
              │  • 수입 압력 플래그 모듈        │
              │  • 처방 의사결정 트리           │
              │                               │
              │  스케줄러: APScheduler          │
              └──────────────┬────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │     처방 결과 → PostgreSQL    │
              │     → 앱 Push 알림 API        │
              └──────────────────────────────┘
```

---

## 2. 데이터 소스별 상세 스펙

### 2-1. aT KAMIS API — 가격·반입량 (핵심)

**역할**: 유통 처방의 1차 입력. 일별 도매·소매 경매가격 + 반입량

**엔드포인트**:
```
GET https://www.kamis.or.kr/service/price/xml.do
    ?action=dailySalesList
    &p_product_cls_code=01      # 01=채소, 02=과일, 03=수산, 04=축산, 05=곡물
    &p_item_code={작목코드}      # 예: 배추=111, 고추=243, 양파=221, 마늘=231
    &p_kind_code=01             # 01=상품, 02=중품
    &p_country_code={시장코드}   # 1101=서울가락, 2100=부산엄궁, 2200=대구북부
    &p_regday={YYYY-MM-DD}
    &p_convert_kg_yn=Y          # kg 단위 환산
```

**주요 작목 코드 (밭농업 기계화 8개 + 5대 과수)**:
```python
CROP_CODES = {
    # 채소류 (p_product_cls_code=01)
    '배추': '111', '무': '112', '양파': '221', '마늘': '231',
    '대파': '261', '고추': '243', '감자': '152', '콩': '111',  # 콩 별도 확인 필요
    # 과수류 (p_product_cls_code=02)
    '사과': '411', '배': '412', '복숭아': '415',
    '포도': '414', '감귤': '417',
}

MARKET_CODES = {
    '가락': '1101', '강서': '1104', '구리': '1302',
    '부산엄궁': '2100', '대구북부': '2200', '광주각화': '3100',
}
```

**수집 스케줄**: 매일 오전 06:00 (전일 데이터 확정 후)

**InfluxDB 스키마**:
```
measurement: kamis_price
tags:
  - crop_code (작목코드)
  - crop_name (작목명)
  - market_code (시장코드)
  - grade (등급: 상/중)
fields:
  - price_per_kg (float) — 도매경매가 원/kg
  - volume_kg (float) — 반입량 kg
  - retail_price (float) — 소매가 (별도 endpoint)
timestamp: 해당 날짜 00:00:00 UTC+9
```

**과거 데이터 초기 수집**: 파이프라인 구축 즉시 5년치(2020~) 일괄 수집 → 계절성 베이스라인 구축

---

### 2-2. 관세청 수출입무역통계 API — 수입 농산물

**역할**: 국산 도매가에 간접 영향을 주는 수입 압력 지표

**엔드포인트**:
```
GET https://unipass.customs.go.kr/ets/index.do  # 공공데이터포털 연계
또는
GET https://www.data.go.kr/data/15057079/openapi.do
    ?serviceKey={API키}
    &hsSgn={HS코드}    # 6자리
    &qryYymm={YYYYMM}
    &ctrCd={국가코드}   # 전체: 공백
```

**주요 HS 코드**:
```python
HS_CODES = {
    '고추·고추분': '090421',   # 건고추, 고추분
    '마늘': '070320',
    '양파': '070310',
    '배추류': '070490',        # 양배추·배추 포함
    '감자': '070190',
    '대파': '070900',          # 기타 채소 포함
}
```

**수집 스케줄**: 매월 1일 (전월 확정치)

**PostgreSQL 스키마**:
```sql
CREATE TABLE import_trade (
    id SERIAL PRIMARY KEY,
    hs_code VARCHAR(10),
    crop_name VARCHAR(50),
    year_month CHAR(6),           -- YYYYMM
    import_qty_kg BIGINT,         -- 수입량 (kg)
    import_value_usd INTEGER,     -- 수입금액 (USD)
    unit_price_usd NUMERIC(10,4), -- kg당 단가
    country_code VARCHAR(5),      -- 주요 수출국
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Phase별 활용**:
- PoC~Phase 1: 수집·적재만. 모델 미통합
- Phase 2: 전월 수입량 급증(+30% YoY) 시 해당 작목 처방에 "수입 압력 주의" 플래그 추가

---

### 2-3. 통계청 KOSIS API — 재배면적·생산량

**역할**: 계절성 모델의 연간 보정값. 수급 중기 베이스라인

**엔드포인트**:
```
GET https://kosis.kr/openapi/Param/statisticsParamData.do
    ?method=getList
    &apiKey={키}
    &itmId=T10+T20+T30    # 재배면적, 수확면적, 생산량
    &objL1={작목코드}
    &format=json
    &jsonVD=Y
```

**주요 통계표**:
```python
KOSIS_TABLE_IDS = {
    '채소류_재배현황': '101_DT_1ET0005',  # 채소류 작목별 재배면적·생산량
    '과수류_재배현황': '101_DT_1ET0006',  # 과수류 작목별
    '특용작물': '101_DT_1ET0007',
}
```

**수집 스케줄**: 연 1회 (매년 2월, 전년도 확정치 공표 후)

**PostgreSQL 스키마**:
```sql
CREATE TABLE crop_area_stats (
    id SERIAL PRIMARY KEY,
    year INTEGER,
    crop_name VARCHAR(50),
    crop_code VARCHAR(20),
    cultivation_area_ha NUMERIC(10,1),   -- 재배면적 (ha)
    harvest_area_ha NUMERIC(10,1),       -- 수확면적 (ha)
    production_ton NUMERIC(12,1),        -- 생산량 (톤)
    yield_per_10a NUMERIC(8,1),          -- 10a당 수확량 (kg)
    source VARCHAR(50) DEFAULT 'KOSIS',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

### 2-4. KREI 농업관측월보 — 재배의향면적 (선행지표)

**역할**: 통계청 확정치보다 6~9개월 앞서는 핵심 선행 지표. "올해 농가들이 배추를 얼마나 심을 계획인지"

**수집 방법**: 크롤링 (API 미제공)
```
URL: https://aglook.krei.re.kr/  # 농업관측센터
또는 PDF: https://aglook.krei.re.kr/web/sub/report01.do
    → 월별 채소관측, 과일관측, 곡물관측 보고서 PDF
```

**크롤링 스케줄**: 매월 15일 전후 (발행 직후)

**파싱 전략**:
```python
# PDF 파싱: pdfminer 또는 pymupdf
# 핵심 추출 항목:
#   - 작목명, 재배의향면적 (전년비 %), 생육 상황, 출하 전망
# 정형화 어려우므로 초기에는 수동 입력 + 자동화 점진 도입

KREI_PARSE_TARGETS = {
    '재배의향면적_전년비': r'재배의향면적.*?(\+|-)\s*(\d+\.?\d*)%',
    '출하전망': r'출하.*?(증가|감소|보합)',
    '주산지_생육': r'생육.*?(양호|불량|보통)',
}
```

**PostgreSQL 스키마**:
```sql
CREATE TABLE krei_outlook (
    id SERIAL PRIMARY KEY,
    year_month CHAR(6),                       -- YYYYMM
    crop_name VARCHAR(50),
    planting_intent_vs_prev_pct NUMERIC(5,1), -- 재배의향면적 전년비 (%)
    growth_status VARCHAR(20),                -- 생육상황 (양호/보통/불량)
    shipment_outlook VARCHAR(20),             -- 출하전망 (증가/보합/감소)
    notes TEXT,                               -- 원문 주요 내용 요약
    source_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**처방 활용 예시**:
```
KREI 3월호: "배추 재배의향면적 전년비 +18%"
→ PostgreSQL 적재
→ 9월 수확기 배추 처방 시 "공급 과잉 위험: 올해 재배의향 18% 증가, 가격 하락 가능성 높음"
→ 작물선택 처방: "내년 배추 면적 축소 검토"
```

---

### 2-5. Sentinel-2 NDVI — 위성 기반 재배면적 추정

**역할**: 공공 통계 의존 없이 주산지 실시간 식생 변화로 재배면적 직접 추정

**데이터 접근**:
```python
# Copernicus Open Access Hub (무료)
# 또는 Google Earth Engine API (무료 비상업 계정)

import ee
ee.Initialize()

# 주요 주산지 폴리곤 정의 후 NDVI 시계열 추출
# 예: 강원 평창 배추 주산지
aoi = ee.Geometry.Polygon([[127.8, 37.3], [128.2, 37.3],
                            [128.2, 37.6], [127.8, 37.6]])

ndvi_collection = (ee.ImageCollection('COPERNICUS/S2_SR')
    .filterBounds(aoi)
    .filterDate('2025-01-01', '2025-12-31')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .map(lambda img: img.normalizedDifference(['B8', 'B4'])
         .rename('NDVI')))
```

**수집 스케줄**: 격주 (Sentinel-2 회귀주기 5일, 운량 필터링 후 유효 데이터 격주 수준)

**InfluxDB 스키마**:
```
measurement: sentinel_ndvi
tags:
  - region (주산지명: 평창, 진주, 해남 등)
  - crop_zone (작목구역: 배추, 고추 등)
fields:
  - ndvi_mean (float) — 구역 평균 NDVI
  - ndvi_std (float) — 표준편차
  - cloud_cover_pct (float) — 운량
  - valid_pixel_pct (float) — 유효 픽셀 비율
timestamp: 영상 촬영일 UTC
```

---

## 3. 처방 엔진 — 알고리즘 상세

### 3-1. GDD 기반 수확 가능 시점 추정

```python
# Growing Degree Days 계산
T_BASE = {
    '고추': 10.0, '배추': 5.0, '양파': 7.0,
    '마늘': 5.0,  '감자': 7.0, '대파': 5.0,
    '사과': 5.0,  '포도': 10.0, '복숭아': 7.0,
}

# 수확 임계 GDD (농진청 생육 연구 기반 — 초기값, 현장 데이터로 보정)
HARVEST_GDD_THRESHOLD = {
    '고추': 2800, '배추': 900, '양파': 1800,
    '마늘': 1200, '감자': 1400,
}

def calc_gdd(t_max: float, t_min: float, crop: str) -> float:
    t_base = T_BASE[crop]
    t_mean = (t_max + t_min) / 2
    return max(0, t_mean - t_base)

def estimate_harvest_date(planting_date: date, crop: str,
                          weather_forecast: list[dict]) -> date:
    """파종일 + 기상예보 → 수확 예상일 반환"""
    cumulative_gdd = 0.0
    threshold = HARVEST_GDD_THRESHOLD[crop]

    for day_weather in weather_forecast:
        daily_gdd = calc_gdd(day_weather['t_max'], day_weather['t_min'], crop)
        cumulative_gdd += daily_gdd
        if cumulative_gdd >= threshold:
            return day_weather['date']

    return None  # 예보 범위 내 미도달
```

---

### 3-2. 가격 계절성 분석 — STL 분해

```python
from statsmodels.tsa.seasonal import STL
import pandas as pd

def build_seasonal_baseline(crop_code: str, market_code: str,
                             years: int = 5) -> dict:
    """
    과거 N년 KAMIS 데이터로 작목별 주간 가격 계절성 패턴 구축
    Returns: {week_of_year: {'q25': float, 'q50': float, 'q75': float}}
    """
    df = query_influxdb_price(crop_code, market_code, years)
    df = df.resample('W').mean()  # 주간 평균

    stl = STL(df['price_per_kg'], period=52, robust=True)
    result = stl.fit()

    seasonal_pattern = {}
    df['seasonal'] = result.seasonal
    df['week'] = df.index.isocalendar().week

    for week, group in df.groupby('week'):
        seasonal_pattern[week] = {
            'q25': group['price_per_kg'].quantile(0.25),
            'q50': group['price_per_kg'].quantile(0.50),
            'q75': group['price_per_kg'].quantile(0.75),
        }

    return seasonal_pattern


def get_price_percentile(current_price: float, crop_code: str,
                          market_code: str, current_week: int) -> str:
    """현재 가격의 계절성 대비 분위 반환"""
    baseline = load_seasonal_baseline(crop_code, market_code)
    week_stats = baseline[current_week]

    if current_price >= week_stats['q75']:
        return 'HIGH'    # 상위 25% — 고점 구간
    elif current_price <= week_stats['q25']:
        return 'LOW'     # 하위 25% — 저점 구간
    else:
        return 'MIDDLE'
```

---

### 3-3. 반입량 모멘텀 — 선행 지표

```python
def calc_volume_momentum(crop_code: str, market_code: str,
                          lookback_days: int = 7) -> float:
    """
    7일 이동평균 대비 현재 반입량 변화율
    Returns: float (양수 = 반입량 증가, 음수 = 감소)
    양수 큰 값 → 가격 하락 선행 신호
    """
    df = query_influxdb_volume(crop_code, market_code, days=30)
    ma7 = df['volume_kg'].rolling(7).mean()
    current = df['volume_kg'].iloc[-1]
    baseline = ma7.iloc[-1]

    return (current - baseline) / baseline  # 변화율


MOMENTUM_THRESHOLD_UP = 0.15    # +15% 이상 → 가격 하락 위험
MOMENTUM_THRESHOLD_DOWN = -0.10  # -10% 이상 감소 → 가격 상승 가능
```

---

### 3-4. 수입 압력 플래그 (Phase 2~)

```python
def check_import_pressure(crop_name: str) -> dict:
    """
    전월 수입량 YoY 변화율로 수입 압력 플래그 생성
    """
    current = query_import_qty(crop_name, months=1)
    prev_year = query_import_qty(crop_name, months=1, year_offset=-1)

    yoy_change = (current - prev_year) / prev_year

    return {
        'flag': yoy_change > 0.30,          # 30% 이상 급증 시 플래그
        'yoy_pct': round(yoy_change * 100, 1),
        'message': f"수입량 전년비 +{yoy_change*100:.1f}% — 도매가 하락 위험"
                   if yoy_change > 0.30 else None
    }
```

---

### 3-5. 통합 처방 의사결정 엔진

```python
def generate_distribution_prescription(farm_id: str,
                                        crop_name: str) -> dict:
    """
    유통 타이밍 처방 생성 메인 함수
    """
    farm = get_farm_info(farm_id)
    crop_code = CROP_CODES[crop_name]
    market_code = get_nearest_market(farm['location'])

    # 1. 수확 가능 여부 확인
    harvest_ready, days_until_harvest = check_harvest_readiness(
        farm_id, crop_name
    )

    if not harvest_ready:
        return {
            'type': 'HARVEST_PENDING',
            'message': f"수확까지 약 {days_until_harvest}일 남음",
            'prescription': None
        }

    # 2. 현재 가격 분위
    current_price = get_latest_price(crop_code, market_code)
    current_week = date.today().isocalendar().week
    price_position = get_price_percentile(current_price, crop_code,
                                           market_code, current_week)

    # 3. 반입량 모멘텀
    momentum = calc_volume_momentum(crop_code, market_code)

    # 4. 수입 압력 (Phase 2~)
    import_flag = check_import_pressure(crop_name)

    # 5. 저장 가능 여부
    storable = STORABLE_CROPS.get(crop_name, False)

    # 6. 처방 결정 트리
    if price_position == 'HIGH':
        prescription = 'SHIP_NOW'
        reason = f"현재 가격 {current_price}원/kg — 평년 동기 대비 상위 25% 고점"

    elif price_position == 'LOW':
        if storable:
            prescription = 'WAIT'
            reason = f"현재 가격 저점. {crop_name}은 저장 가능 — 가격 회복 대기"
        else:
            prescription = 'SHIP_NOW'
            reason = f"현재 가격 저점이나 {crop_name}은 장기 저장 불가 — 품질 손실 전 즉시 출하"

    else:  # MIDDLE
        if momentum > MOMENTUM_THRESHOLD_UP:
            prescription = 'SHIP_WITHIN_WEEK'
            reason = f"반입량 전주 대비 +{momentum*100:.0f}% 증가 — 3~5일 내 가격 하락 가능"
        elif momentum < MOMENTUM_THRESHOLD_DOWN:
            prescription = 'WAIT_7_10'
            reason = f"반입량 감소세 — 7~10일 후 가격 개선 가능"
        else:
            prescription = 'MONITOR'
            reason = "현재 가격 중간 구간, 반입량 보합 — 3일 후 재판단"

    # 7. 수입 압력 플래그 추가
    if import_flag['flag']:
        reason += f"\n⚠️ {import_flag['message']}"

    return {
        'type': 'DISTRIBUTION',
        'prescription': prescription,
        'current_price': current_price,
        'price_position': price_position,
        'momentum_pct': round(momentum * 100, 1),
        'reason': reason,
        'market': market_code,
        'generated_at': datetime.now().isoformat()
    }


# 저장 가능 작목 분류
STORABLE_CROPS = {
    '마늘': True,   # 저온 저장 6~12개월
    '양파': True,   # 저온 저장 3~6개월
    '감자': True,   # 서늘한 곳 2~4개월
    '고추': True,   # 건조 후 장기 보관 가능
    '배추': False,  # 1~2주 내 출하 필요
    '상추': False,  # 수확 후 즉시 출하
    '대파': False,  # 1~2주 내 출하
}
```

---

## 4. 스케줄러 구성 (APScheduler)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# 고빈도 수집
scheduler.add_job(collect_kamis_price,      'cron', hour=6, minute=0)   # 매일 06:00
scheduler.add_job(collect_weather_data,     'cron', minute=0)           # 매시간
scheduler.add_job(collect_sentinel_ndvi,    'cron', day_of_week='mon,thu') # 격주

# 저빈도 수집
scheduler.add_job(collect_import_trade,     'cron', day=1,  hour=9)     # 매월 1일
scheduler.add_job(collect_kosis_crop_area,  'cron', month=2, day=15)    # 연 1회 2월
scheduler.add_job(crawl_krei_outlook,       'cron', day=15, hour=10)    # 매월 15일

# 처방 생성
scheduler.add_job(run_distribution_prescriptions,  'cron', hour=7)     # 매일 07:00
scheduler.add_job(rebuild_seasonal_baselines,       'cron', day=1)      # 매월 baseline 재계산

scheduler.start()
```

---

## 5. PoC → Phase 2 구현 단계별 계획

| 단계 | 구현 항목 | 목표 |
|------|---------|------|
| **PoC (0~6개월)** | aT KAMIS 파이프라인 구축 + 5년치 과거 데이터 수집 | 계절성 베이스라인 확보 |
| **PoC (0~6개월)** | 통계청 KOSIS 재배면적 수집 | 연간 수급 기준 테이블 구축 |
| **PoC (0~6개월)** | 관세청 수출입통계 파이프라인 구축 | 수집·적재만 (모델 미통합) |
| **PoC (3~6개월)** | GDD 수확시점 추정 모듈 구현 | 파종일 입력 → 수확 예상일 계산 |
| **Phase 1 (6~12개월)** | KREI 농업관측월보 크롤러 구현 | 월별 재배의향면적 자동 적재 |
| **Phase 1 (6~12개월)** | 가격 계절성 분석 모듈 + 반입량 모멘텀 모듈 구현 | 처방 생성 로직 작동 |
| **Phase 1 (6~12개월)** | 유통 처방 앱 알림 통합 | "이번 주 출하 권장" 첫 처방 발송 |
| **Phase 2 (12~24개월)** | 수입 압력 플래그 모델 통합 | 고추·마늘·양파 수입 모니터링 |
| **Phase 2 (12~24개월)** | 시장별 가격 편차 분석 → 출하 채널 처방 | "가락 vs 강서" 최적 채널 처방 |
| **Phase 2 (12~24개월)** | Sentinel-2 NDVI 재배면적 추정 모듈 | 통계청 선행하는 실시간 면적 추정 |

---

## 6. 알려진 한계 및 리스크

| 리스크 | 내용 | 대응 |
|--------|------|------|
| **KAMIS 데이터 공백** | 명절 전후 데이터 수집 불안정, 일부 작목 누락 | 결측값 보간 (선형) + 이상값 필터 |
| **KREI 월보 파싱 실패** | PDF 레이아웃 변경 시 크롤러 파싱 오류 | 파싱 실패 시 Slack 알림 + 수동 입력 fallback |
| **단일 시장 의존** | 가락시장 데이터만으로는 지역별 가격 편차 미반영 | 농가 소재지 기준 인접 도매시장 우선 + 가락 보조 |
| **GDD 모델 초기 오차** | 품종·미기후 차이로 초기 예측 오차 ±10~15일 | PoC 현장 데이터로 작물별 Kc 보정과 동일하게 임계값 보정 |
| **수입 데이터 지연** | 관세청 확정치 1~2개월 지연 | 잠정치 사용 + 확정치 수신 시 소급 업데이트 |

---

## 7. 개발 환경 및 의존성

```
# Python 핵심 패키지
fastapi>=0.110
influxdb-client>=1.40
psycopg2-binary>=2.9
apscheduler>=3.10
statsmodels>=0.14      # STL 분해
pandas>=2.0
requests>=2.31
pdfminer.six>=20221105 # KREI 월보 PDF 파싱
google-earth-engine    # Sentinel-2

# 인프라
AWS IoT Core          # MQTT 브로커
AWS EC2 (t3.medium)   # 처방 엔진 서버
InfluxDB 2.x          # 시계열 DB (Cloud 또는 자체 호스팅)
PostgreSQL 15         # 마스터 DB (AWS RDS 또는 자체)
```

---

> **다음 업데이트 예정**: Phase 1 현장 데이터 축적 후 GDD 임계값 보정 결과 반영, KREI 크롤러 실제 구현 코드 추가
