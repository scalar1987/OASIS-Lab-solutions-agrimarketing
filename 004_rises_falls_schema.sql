-- 가격 등락 정보 (전국 평균) 테이블
CREATE TABLE IF NOT EXISTS price_rises_falls (
    id              BIGSERIAL PRIMARY KEY,
    data_date       DATE        NOT NULL,
    crop_name       VARCHAR     NOT NULL,
    ctgry_cd        VARCHAR,
    item_cd         VARCHAR,
    vrty_cd         VARCHAR,
    vrty_nm         VARCHAR,
    grd_cd          VARCHAR,
    se_cd           VARCHAR,        -- 01:소매, 02:중도매
    unit            VARCHAR,
    unit_sz         VARCHAR,
    avg_price       NUMERIC,        -- 조사일 평균가격
    avg_price_per_kg NUMERIC,       -- kg 환산 평균가격
    dd1_change_rate  NUMERIC,       -- 1일전 등락율 (%)
    ww1_change_rate  NUMERIC,       -- 1주일전 등락율 (%)
    mm1_change_rate  NUMERIC,       -- 1개월전 등락율 (%)
    yy1_change_rate  NUMERIC,       -- 1년전 등락율 (%)
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rises_falls_unique
    ON price_rises_falls (data_date, crop_name, se_cd, vrty_cd, grd_cd);

CREATE INDEX IF NOT EXISTS idx_rises_falls_crop_date
    ON price_rises_falls (crop_name, data_date DESC);

ALTER TABLE price_rises_falls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read price_rises_falls"
    ON price_rises_falls FOR SELECT USING (true);
