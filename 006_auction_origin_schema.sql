-- 경매원천정보 테이블
CREATE TABLE IF NOT EXISTS auction_origin (
    id              BIGSERIAL PRIMARY KEY,
    trd_clcln_ymd   DATE        NOT NULL,       -- 거래정산일자
    whsl_mrkt_cd    VARCHAR     NOT NULL,       -- 도매시장코드
    whsl_mrkt_nm    VARCHAR,                    -- 도매시장명
    corp_cd         VARCHAR,                    -- 법인코드
    corp_nm         VARCHAR,                    -- 법인명
    spm_no          VARCHAR,                    -- 원표번호
    auctn_seq       VARCHAR,                    -- 경매순서
    auctn_seq2      VARCHAR,                    -- 경매순서2
    trd_se          VARCHAR,                    -- 매매구분
    gds_lclsf_cd    VARCHAR,                    -- 상품대분류코드
    gds_lclsf_nm    VARCHAR,                    -- 상품대분류명
    gds_mclsf_cd    VARCHAR,                    -- 상품중분류코드
    gds_mclsf_nm    VARCHAR,                    -- 상품중분류명
    gds_sclsf_cd    VARCHAR,                    -- 상품소분류코드
    gds_sclsf_nm    VARCHAR,                    -- 상품소분류명
    corp_gds_item_nm VARCHAR,                   -- 법인상품품목명
    corp_gds_vrty_nm VARCHAR,                   -- 법인상품품종명
    unit_qty        NUMERIC,                    -- 단위물량
    unit_nm         VARCHAR,                    -- 단위명
    pkg_nm          VARCHAR,                    -- 포장명
    sz_nm           VARCHAR,                    -- 크기명
    grd_cd          VARCHAR,                    -- 등급코드
    grd_nm          VARCHAR,                    -- 등급명
    qty             NUMERIC,                    -- 물량
    scsbd_prc       NUMERIC,                    -- 낙찰가
    plor_cd         VARCHAR,                    -- 원산지코드
    plor_nm         VARCHAR,                    -- 원산지명
    spmt_se         VARCHAR,                    -- 출하구분
    unit_tot_qty    NUMERIC,                    -- 단위총물량
    totprc          NUMERIC,                    -- 총가격
    scsbd_dt        VARCHAR,                    -- 낙찰일시
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auction_origin_unique
    ON auction_origin (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, spm_no, auctn_seq, auctn_seq2);

CREATE INDEX IF NOT EXISTS idx_auction_origin_date_market
    ON auction_origin (trd_clcln_ymd DESC, whsl_mrkt_cd);

CREATE INDEX IF NOT EXISTS idx_auction_origin_item
    ON auction_origin (gds_mclsf_nm, trd_clcln_ymd DESC);

ALTER TABLE auction_origin ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public read auction_origin"
    ON auction_origin FOR SELECT USING (true);
