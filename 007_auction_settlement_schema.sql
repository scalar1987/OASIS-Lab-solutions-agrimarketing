
- 경매 정산정보 테이블 (katSale)
CREATE TABLE IF NOT EXISTS auction_settlement (
    id              BIGSERIAL PRIMARY KEY,
    trd_clcln_ymd   DATE        NOT NULL,       -- 거래정산일자
    whsl_mrkt_cd    VARCHAR     NOT NULL,       -- 도매시장코드
    whsl_mrkt_nm    VARCHAR,                    -- 도매시장명
    corp_cd         VARCHAR,                    -- 법인코드
    corp_nm         VARCHAR,                    -- 법인명
    trd_se          VARCHAR,                    -- 매매구분
    gds_lclsf_cd    VARCHAR,                    -- 상품대분류코드
    gds_lclsf_nm    VARCHAR,                    -- 상품대분류명
    gds_mclsf_cd    VARCHAR,                    -- 상품중분류코드
    gds_mclsf_nm    VARCHAR,                    -- 상품중분류명
    gds_sclsf_cd    VARCHAR,                    -- 상품소분류코드
    gds_sclsf_nm    VARCHAR,                    -- 상품소분류명
    unit_cd         VARCHAR,                    -- 단위코드
    unit_nm         VARCHAR,                    -- 단위명
    unit_qty        NUMERIC,                    -- 단위물량
    pkg_cd          VARCHAR,                    -- 포장코드
    pkg_nm          VARCHAR,                    -- 포장명
    sz_cd           VARCHAR,                    -- 크기코드
    sz_nm           VARCHAR,                    -- 크기명
    grd_cd          VARCHAR,                    -- 등급코드
    grd_nm          VARCHAR,                    -- 등급명
    plor_cd         VARCHAR,                    -- 원산지코드
    plor_nm         VARCHAR,                    -- 원산지명
    unit_tot_qty    NUMERIC,                    -- 단위총물량
    totprc          NUMERIC,                    -- 총가격
    avgprc          NUMERIC,                    -- 평균가격
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auction_settlement_unique
    ON auction_settlement (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, gds_lclsf_cd,
                           gds_mclsf_cd, gds_sclsf_cd, unit_cd, pkg_cd, sz_cd,
                           grd_cd, plor_cd, trd_se);

CREATE INDEX IF NOT EXISTS idx_auction_settlement_date_market
    ON auction_settlement (trd_clcln_ymd DESC, whsl_mrkt_cd);

CREATE INDEX IF NOT EXISTS idx_auction_settlement_item
    ON auction_settlement (gds_mclsf_nm, trd_clcln_ymd DESC);

ALTER TABLE auction_settlement ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read auction_settlement"
    ON auction_settlement FOR SELECT USING (true);
