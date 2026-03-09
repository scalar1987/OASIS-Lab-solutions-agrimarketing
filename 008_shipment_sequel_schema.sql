-- 출하량 추이 정보 테이블
CREATE TABLE IF NOT EXISTS shipment_sequel (
    id              BIGSERIAL PRIMARY KEY,
    spmt_ymd        DATE        NOT NULL,       -- 출하일자
    whsl_mrkt_cd    VARCHAR     NOT NULL,       -- 도매시장코드
    whsl_mrkt_nm    VARCHAR,                    -- 도매시장명
    corp_cd         VARCHAR,                    -- 법인코드
    corp_nm         VARCHAR,                    -- 법인명
    gds_lclsf_cd    VARCHAR,                    -- 상품대분류코드
    gds_lclsf_nm    VARCHAR,                    -- 상품대분류명
    gds_mclsf_cd    VARCHAR,                    -- 상품중분류코드
    gds_mclsf_nm    VARCHAR,                    -- 상품중분류명
    gds_sclsf_cd    VARCHAR,                    -- 상품소분류코드
    gds_sclsf_nm    VARCHAR,                    -- 상품소분류명
    unit_cd         VARCHAR,                    -- 단위코드
    unit_nm         VARCHAR,                    -- 단위명
    unit_qty        NUMERIC,                    -- 단위물량
    avg_spmt_qty    NUMERIC,                    -- 평균출하수량
    avg_spmt_amt    NUMERIC,                    -- 평균출하량
    ww1_avg_spmt_qty NUMERIC,                   -- 1주일전 평균출하수량
    ww1_avg_spmt_amt NUMERIC,                   -- 1주일전 평균출하량
    ww2_avg_spmt_qty NUMERIC,                   -- 2주일전 평균출하수량
    ww2_avg_spmt_amt NUMERIC,                   -- 2주일전 평균출하량
    ww3_avg_spmt_qty NUMERIC,                   -- 3주일전 평균출하수량
    ww3_avg_spmt_amt NUMERIC,                   -- 3주일전 평균출하량
    ww4_avg_spmt_qty NUMERIC,                   -- 4주일전 평균출하수량
    ww4_avg_spmt_amt NUMERIC,                   -- 4주일전 평균출하량
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shipment_sequel_unique
    ON shipment_sequel (spmt_ymd, whsl_mrkt_cd, corp_cd, gds_lclsf_cd, gds_mclsf_cd, gds_sclsf_cd);

CREATE INDEX IF NOT EXISTS idx_shipment_sequel_date_market
    ON shipment_sequel (spmt_ymd DESC, whsl_mrkt_cd);

CREATE INDEX IF NOT EXISTS idx_shipment_sequel_item
    ON shipment_sequel (gds_mclsf_nm, spmt_ymd DESC);

ALTER TABLE shipment_sequel ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read shipment_sequel"
    ON shipment_sequel FOR SELECT USING (true);
