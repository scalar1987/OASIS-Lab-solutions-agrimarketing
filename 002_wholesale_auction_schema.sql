-- 002_wholesale_auction_schema.sql
-- PostgreSQL schema draft for auction origin / settlement / shipment sequel

CREATE TABLE IF NOT EXISTS auction_origin_trades (
    id BIGSERIAL PRIMARY KEY,
    trd_clcln_ymd DATE NOT NULL,
    whsl_mrkt_cd VARCHAR(10) NOT NULL,
    whsl_mrkt_nm VARCHAR(100),
    corp_cd VARCHAR(20),
    corp_nm VARCHAR(100),
    spm_no VARCHAR(40),
    auctn_seq VARCHAR(20),
    auctn_seq2 VARCHAR(20),
    trd_se VARCHAR(10),
    gds_lclsf_cd VARCHAR(20),
    gds_lclsf_nm VARCHAR(100),
    gds_mclsf_cd VARCHAR(20),
    gds_mclsf_nm VARCHAR(100),
    gds_sclsf_cd VARCHAR(20),
    gds_sclsf_nm VARCHAR(100),
    corp_gds_cd VARCHAR(40),
    corp_gds_item_nm VARCHAR(100),
    corp_gds_vrty_nm VARCHAR(100),
    unit_qty NUMERIC(14,4),
    unit_cd VARCHAR(20),
    unit_nm VARCHAR(50),
    pkg_cd VARCHAR(20),
    pkg_nm VARCHAR(50),
    sz_cd VARCHAR(20),
    sz_nm VARCHAR(50),
    grd_cd VARCHAR(20),
    grd_nm VARCHAR(50),
    qty NUMERIC(14,4),
    scsbd_prc NUMERIC(14,2),
    unit_tot_qty NUMERIC(16,4),
    totprc NUMERIC(18,2),
    plor_cd VARCHAR(20),
    plor_nm VARCHAR(100),
    spmt_se VARCHAR(20),
    scsbd_dt TIMESTAMP,
    raw JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, spm_no, auctn_seq, auctn_seq2)
);

CREATE INDEX IF NOT EXISTS idx_auction_origin_date_market
    ON auction_origin_trades (trd_clcln_ymd, whsl_mrkt_cd);

CREATE TABLE IF NOT EXISTS auction_settlement_daily (
    id BIGSERIAL PRIMARY KEY,
    trd_clcln_ymd DATE NOT NULL,
    whsl_mrkt_cd VARCHAR(10) NOT NULL,
    whsl_mrkt_nm VARCHAR(100),
    corp_cd VARCHAR(20),
    corp_nm VARCHAR(100),
    gds_lclsf_cd VARCHAR(20),
    gds_lclsf_nm VARCHAR(100),
    gds_mclsf_cd VARCHAR(20),
    gds_mclsf_nm VARCHAR(100),
    gds_sclsf_cd VARCHAR(20),
    gds_sclsf_nm VARCHAR(100),
    trd_se VARCHAR(10),
    unit_qty NUMERIC(14,4),
    unit_cd VARCHAR(20),
    unit_nm VARCHAR(50),
    pkg_cd VARCHAR(20),
    pkg_nm VARCHAR(50),
    sz_cd VARCHAR(20),
    sz_nm VARCHAR(50),
    grd_cd VARCHAR(20),
    grd_nm VARCHAR(50),
    plor_cd VARCHAR(20),
    plor_nm VARCHAR(100),
    unit_tot_qty NUMERIC(16,4),
    totprc NUMERIC(18,2),
    avgprc NUMERIC(14,2),
    lwprc NUMERIC(14,2),
    hgprc NUMERIC(14,2),
    raw JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, gds_lclsf_cd, gds_mclsf_cd, gds_sclsf_cd, unit_cd, pkg_cd, sz_cd, grd_cd, plor_cd, trd_se)
);

CREATE INDEX IF NOT EXISTS idx_auction_settlement_date_market
    ON auction_settlement_daily (trd_clcln_ymd, whsl_mrkt_cd);

CREATE TABLE IF NOT EXISTS shipment_sequel_daily (
    id BIGSERIAL PRIMARY KEY,
    spmt_ymd DATE NOT NULL,
    whsl_mrkt_cd VARCHAR(10),
    whsl_mrkt_nm VARCHAR(100),
    corp_cd VARCHAR(20),
    corp_nm VARCHAR(100),
    gds_lclsf_cd VARCHAR(20),
    gds_lclsf_nm VARCHAR(100),
    gds_mclsf_cd VARCHAR(20),
    gds_mclsf_nm VARCHAR(100),
    gds_sclsf_cd VARCHAR(20),
    gds_sclsf_nm VARCHAR(100),
    unit_cd VARCHAR(20),
    unit_nm VARCHAR(50),
    unit_qty NUMERIC(14,4),
    avg_spmt_qty NUMERIC(16,4),
    avg_spmt_amt NUMERIC(18,2),
    ww1_bfr_avg_spmt_qty NUMERIC(16,4),
    ww1_bfr_avg_spmt_amt NUMERIC(18,2),
    ww2_bfr_avg_spmt_qty NUMERIC(16,4),
    ww2_bfr_avg_spmt_amt NUMERIC(18,2),
    ww3_bfr_avg_spmt_qty NUMERIC(16,4),
    ww3_bfr_avg_spmt_amt NUMERIC(18,2),
    ww4_bfr_avg_spmt_qty NUMERIC(16,4),
    ww4_bfr_avg_spmt_amt NUMERIC(18,2),
    raw JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (spmt_ymd, whsl_mrkt_cd, corp_cd, gds_lclsf_cd, gds_mclsf_cd, gds_sclsf_cd)
);

CREATE INDEX IF NOT EXISTS idx_shipment_sequel_date_market
    ON shipment_sequel_daily (spmt_ymd, whsl_mrkt_cd);
