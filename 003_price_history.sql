-- 003_price_history.sql
-- perDay API 원시 데이터 전체 컬럼 저장 (등급별 가격 포함)
-- 기존 테이블이 있으면 삭제 후 재생성

DROP TABLE IF EXISTS price_history CASCADE;

CREATE TABLE price_history (
    id                BIGSERIAL PRIMARY KEY,
    exmn_ymd          DATE         NOT NULL,    -- 조사일자
    se_cd             VARCHAR(5),               -- 구분코드 (01:소매, 02:중도매)
    se_nm             VARCHAR(20),              -- 구분명
    ctgry_cd          VARCHAR(10),              -- 부류코드
    ctgry_nm          VARCHAR(50),              -- 부류명
    item_cd           VARCHAR(10)  NOT NULL,    -- 품목코드
    item_nm           VARCHAR(50),              -- 품목명
    vrty_cd           VARCHAR(10),              -- 품종코드
    vrty_nm           VARCHAR(50),              -- 품종명
    grd_cd            VARCHAR(5),               -- 등급코드 (04:상품, 05:중품, 06:하품)
    grd_nm            VARCHAR(20),              -- 등급명
    sigungu_cd        VARCHAR(10),              -- 시군구코드
    sigungu_nm        VARCHAR(50),              -- 시군구명
    unit              VARCHAR(10),              -- 단위
    unit_sz           VARCHAR(10),              -- 단위크기
    mrkt_cd           VARCHAR(20)  NOT NULL,    -- 시장코드
    mrkt_nm           VARCHAR(100),             -- 시장명
    exmn_dd_prc       NUMERIC(14,2),            -- 조사일가격
    exmn_dd_cnvs_prc  NUMERIC(14,4),            -- 조사일kg환산가격
    orgn_rgstr_dt     TIMESTAMPTZ,              -- 원본등록일시
    crop_name         VARCHAR(50),              -- 작물명 (내부 매핑)
    created_at        TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (exmn_ymd, se_cd, item_cd, vrty_cd, grd_cd, mrkt_cd)
);

CREATE INDEX idx_price_history_crop_date
    ON price_history (crop_name, exmn_ymd DESC);

CREATE INDEX idx_price_history_item_mrkt
    ON price_history (item_cd, mrkt_cd, exmn_ymd DESC);

ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read price_history"
    ON price_history FOR SELECT USING (true);
