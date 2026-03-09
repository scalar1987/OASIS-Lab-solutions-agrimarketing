-- ============================================================
-- OASIS Market — Supabase 초기 스키마
-- supabase/migrations/001_initial_schema.sql
-- ============================================================

-- ── 처방 결과 ──────────────────────────────────────────────────
CREATE TABLE prescriptions (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    -- 대상
    crop_name       VARCHAR(50)  NOT NULL,   -- 배추, 고추, 양파 ...
    crop_code       VARCHAR(10),             -- KAMIS 작목 코드

    -- 처방
    rx_type         VARCHAR(30)  NOT NULL,
    -- SHIP_NOW | SHIP_WITHIN_WEEK | WAIT | SHIP_NOW_URGENT | MONITOR
    rx_message      TEXT         NOT NULL,   -- 농가 표시용 한 줄 처방
    rx_reason       TEXT,                    -- 처방 근거 (상세)
    rx_sms          TEXT,                    -- SMS 발송용 텍스트

    -- 분석 수치
    current_price   INTEGER,                 -- 원/kg
    price_percentile NUMERIC(5,1),           -- 계절성 대비 분위 (0~100)
    volume_momentum  NUMERIC(6,1),           -- 반입량 모멘텀 % (-100~100)
    storable        BOOLEAN,

    -- 메타
    market_code     VARCHAR(10)  DEFAULT '1101',  -- 1101=가락
    data_date       DATE         NOT NULL,         -- 기준 날짜
    engine_version  VARCHAR(20)  DEFAULT 'v0.1'
);

-- 최신 처방 조회용 인덱스
CREATE INDEX idx_prescriptions_crop_date
    ON prescriptions (crop_name, data_date DESC);

-- ── 재배면적 통계 (통계청 KOSIS, 연 1회) ──────────────────────
CREATE TABLE crop_area_stats (
    id                    BIGSERIAL PRIMARY KEY,
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    year                  SMALLINT     NOT NULL,
    crop_name             VARCHAR(50)  NOT NULL,
    crop_code             VARCHAR(20),
    cultivation_area_ha   NUMERIC(10,1),   -- 재배면적 (ha)
    harvest_area_ha       NUMERIC(10,1),   -- 수확면적 (ha)
    production_ton        NUMERIC(12,1),   -- 생산량 (톤)
    yield_per_10a         NUMERIC(8,1),    -- 10a당 수확량 (kg)
    source                VARCHAR(50)  DEFAULT 'KOSIS',

    UNIQUE (year, crop_name)
);

-- ── KREI 농업관측월보 (재배의향면적, 월 1회) ───────────────────
CREATE TABLE krei_outlook (
    id                          BIGSERIAL PRIMARY KEY,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),

    year_month                  CHAR(6)      NOT NULL,  -- YYYYMM
    crop_name                   VARCHAR(50)  NOT NULL,
    planting_intent_vs_prev_pct NUMERIC(5,1),           -- 재배의향 전년비 %
    growth_status               VARCHAR(20),             -- 양호/보통/불량
    shipment_outlook            VARCHAR(20),             -- 증가/보합/감소
    notes                       TEXT,
    source_url                  TEXT,

    UNIQUE (year_month, crop_name)
);

-- ── 작목 마스터 ────────────────────────────────────────────────
CREATE TABLE crops (
    id           SMALLSERIAL PRIMARY KEY,
    crop_name    VARCHAR(50)  UNIQUE NOT NULL,
    crop_code    VARCHAR(10)  UNIQUE NOT NULL,   -- KAMIS 코드
    category     VARCHAR(20),                     -- 채소/과수/곡물
    storable     BOOLEAN      DEFAULT FALSE,
    t_base       NUMERIC(4,1),                    -- GDD 기준온도 (°C)
    harvest_gdd  INTEGER,                         -- 수확 임계 GDD
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- 기본 작목 데이터
INSERT INTO crops (crop_name, crop_code, category, storable, t_base, harvest_gdd) VALUES
    ('배추', '211', '채소', FALSE,  5.0,  900),
    ('고추', '243', '채소', TRUE,  10.0, 2800),
    ('양파', '245', '채소', TRUE,   7.0, 1800),
    ('마늘', '244', '채소', TRUE,   5.0, 1200),
    ('대파', '246', '채소', FALSE,  5.0,  800),
    ('감자', '152', '채소', TRUE,   7.0, 1400),
    ('사과', '411', '과수', TRUE,   5.0, 3200),
    ('배',   '412', '과수', TRUE,   5.0, 2800),
    ('포도', '414', '과수', FALSE, 10.0, 2400);

-- ── 농가 프로필 (개인화 등록) ──────────────────────────────────
CREATE TABLE farm_profiles (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- 계정
    user_id             UUID         UNIQUE NOT NULL,  -- Supabase auth.users.id
    owner_name          VARCHAR(100) NOT NULL,

    -- 위치
    sido                VARCHAR(20)  NOT NULL,          -- 예: 경기
    sigungu             VARCHAR(30)  NOT NULL,          -- 예: 이천시
    eupmyeondong        VARCHAR(30),
    latitude            NUMERIC(9,6),
    longitude           NUMERIC(9,6),

    -- 알림 설정
    notification_channel VARCHAR(20) DEFAULT 'push',   -- kakao | sms | push
    notification_hour    SMALLINT    DEFAULT 7         -- 알림 수신 시간대 (0~23)
);

CREATE TABLE farm_crops (
    id                      BIGSERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ DEFAULT NOW(),

    farm_id                 BIGINT      NOT NULL REFERENCES farm_profiles(id) ON DELETE CASCADE,
    crop_name               VARCHAR(50) NOT NULL,
    variety                 VARCHAR(50),               -- 품종 (예: 가을배추)
    cultivation_area_m2     INTEGER,                   -- 재배 면적 (㎡)

    -- 출하처
    primary_channel         VARCHAR(50),               -- 신지공판장 | 가락도매시장 | 농협APC
    shipment_channels       TEXT[],                    -- 복수 출하처

    -- 출하 가능 시점
    planting_date           DATE,
    expected_harvest_start  DATE        NOT NULL,
    expected_harvest_end    DATE        NOT NULL,
    storage_available       BOOLEAN     DEFAULT FALSE,
    storage_capacity_ton    NUMERIC(8,2)
);

CREATE INDEX idx_farm_crops_farm_id ON farm_crops (farm_id);

-- ── Row Level Security (Supabase 권장 설정) ───────────────────
ALTER TABLE prescriptions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE crop_area_stats  ENABLE ROW LEVEL SECURITY;
ALTER TABLE krei_outlook     ENABLE ROW LEVEL SECURITY;
ALTER TABLE crops            ENABLE ROW LEVEL SECURITY;

-- 프론트엔드(anon key)에서 읽기만 허용
CREATE POLICY "public read prescriptions"
    ON prescriptions FOR SELECT USING (true);

CREATE POLICY "public read crops"
    ON crops FOR SELECT USING (true);

CREATE POLICY "public read crop_area_stats"
    ON crop_area_stats FOR SELECT USING (true);

-- service_role(처방 엔진)만 INSERT/UPDATE 가능 — RLS 우회
-- service_role은 RLS를 자동으로 우회하므로 별도 정책 불필요
