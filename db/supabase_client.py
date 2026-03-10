"""
db/supabase_client.py
Supabase 처방 저장 + 가격 이력 저장/조회 (service_role key → RLS 우회)
"""

import os
from datetime import date, timedelta

import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_URL = os.environ["SUPABASE_URL"]
_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def _client() -> Client:
    return create_client(_URL, _KEY)


def save_prescription(rx: dict) -> dict:
    """처방 결과를 prescriptions 테이블에 INSERT."""
    row = {
        "crop_name":        rx["crop_name"],
        "crop_code":        rx.get("crop_code"),
        "rx_type":          rx["rx_type"],
        "rx_message":       rx["rx_message"],
        "rx_reason":        rx.get("rx_reason"),
        "rx_sms":           rx.get("rx_sms"),
        "current_price":    rx.get("current_price"),
        "price_percentile": rx.get("price_percentile"),
        "volume_momentum":  rx.get("volume_momentum"),
        "storable":         rx.get("storable"),
        "market_code":      rx.get("market_code", "1101"),
        "data_date":        rx["data_date"],
        "engine_version":   "v0.1",
    }
    resp = _client().table("prescriptions").insert(row).execute()
    return resp.data[0] if resp.data else {}


def save_price_history(records: list[dict]) -> int:
    """
    가격 데이터를 price_history 테이블에 upsert (배치).
    records 항목: {date_str, crop_name, market_code, market_name, price_per_kg}

    Returns: upsert된 행 수
    """
    if not records:
        return 0
    rows = [
        {
            "data_date":    r["date_str"],
            "crop_name":    r["crop_name"],
            "market_code":  r["market_code"],
            "market_name":  r["market_name"],
            "price_per_kg": round(r["price_per_kg"], 2),
            "volume_kg":    r["volume_kg"] if r.get("volume_kg", 0) > 0 else None,
            "source":       "kamis",
        }
        for r in records
        if r.get("price_per_kg")
    ]
    if not rows:
        return 0
    resp = (
        _client()
        .table("price_history")
        .upsert(rows, on_conflict="data_date,crop_name,market_code")
        .execute()
    )
    return len(resp.data) if resp.data else 0


def save_rises_falls(records: list[dict]) -> int:
    """
    가격 등락 정보를 price_rises_falls 테이블에 upsert.
    Returns: upsert된 행 수
    """
    if not records:
        return 0
    rows = [
        {
            "data_date":        r["data_date"],
            "crop_name":        r["crop_name"],
            "ctgry_cd":         r.get("ctgry_cd"),
            "item_cd":          r.get("item_cd"),
            "vrty_cd":          r.get("vrty_cd"),
            "vrty_nm":          r.get("vrty_nm"),
            "grd_cd":           r.get("grd_cd"),
            "se_cd":            r.get("se_cd"),
            "unit":             r.get("unit"),
            "unit_sz":          r.get("unit_sz"),
            "avg_price":        r.get("avg_price"),
            "avg_price_per_kg": r.get("avg_price_per_kg"),
            "dd1_change_rate":  r.get("dd1_change_rate"),
            "ww1_change_rate":  r.get("ww1_change_rate"),
            "mm1_change_rate":  r.get("mm1_change_rate"),
            "yy1_change_rate":  r.get("yy1_change_rate"),
        }
        for r in records
        if r.get("avg_price_per_kg")
    ]
    if not rows:
        return 0
    resp = (
        _client()
        .table("price_rises_falls")
        .upsert(rows, on_conflict="data_date,crop_name,se_cd,vrty_cd,grd_cd")
        .execute()
    )
    return len(resp.data) if resp.data else 0


def save_auction_origin(records: list[dict]) -> int:
    """
    경매원천정보를 auction_origin 테이블에 upsert.
    Returns: upsert된 행 수
    """
    if not records:
        return 0

    def _safe_numeric(val):
        try:
            if val is None or str(val).strip() == "":
                return None
            return float(str(val).replace(",", ""))
        except Exception:
            return None

    rows = [
        {
            "trd_clcln_ymd":    r.get("trd_clcln_ymd"),
            "whsl_mrkt_cd":     r.get("whsl_mrkt_cd"),
            "whsl_mrkt_nm":     r.get("whsl_mrkt_nm"),
            "corp_cd":          r.get("corp_cd"),
            "corp_nm":          r.get("corp_nm"),
            "spm_no":           r.get("spm_no"),
            "auctn_seq":        r.get("auctn_seq"),
            "auctn_seq2":       r.get("auctn_seq2"),
            "trd_se":           r.get("trd_se"),
            "gds_lclsf_cd":     r.get("gds_lclsf_cd"),
            "gds_lclsf_nm":     r.get("gds_lclsf_nm"),
            "gds_mclsf_cd":     r.get("gds_mclsf_cd"),
            "gds_mclsf_nm":     r.get("gds_mclsf_nm"),
            "gds_sclsf_cd":     r.get("gds_sclsf_cd"),
            "gds_sclsf_nm":     r.get("gds_sclsf_nm"),
            "corp_gds_item_nm": r.get("corp_gds_item_nm"),
            "corp_gds_vrty_nm": r.get("corp_gds_vrty_nm"),
            "unit_qty":         _safe_numeric(r.get("unit_qty")),
            "unit_nm":          r.get("unit_nm"),
            "pkg_nm":           r.get("pkg_nm"),
            "sz_nm":            r.get("sz_nm"),
            "grd_cd":           r.get("grd_cd"),
            "grd_nm":           r.get("grd_nm"),
            "qty":              _safe_numeric(r.get("qty")),
            "scsbd_prc":        _safe_numeric(r.get("scsbd_prc")),
            "plor_cd":          r.get("plor_cd"),
            "plor_nm":          r.get("plor_nm"),
            "spmt_se":          r.get("spmt_se"),
            "unit_tot_qty":     _safe_numeric(r.get("unit_tot_qty")),
            "totprc":           _safe_numeric(r.get("totprc")),
            "scsbd_dt":         r.get("scsbd_dt"),
        }
        for r in records
        if r.get("trd_clcln_ymd") and r.get("whsl_mrkt_cd")
    ]
    if not rows:
        return 0
    total = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        resp = (
            _client()
            .table("auction_origin")
            .upsert(chunk, on_conflict="trd_clcln_ymd,whsl_mrkt_cd,corp_cd,spm_no,auctn_seq,auctn_seq2")
            .execute()
        )
        total += len(resp.data) if resp.data else 0
    return total


def save_auction_settlement(records: list[dict]) -> int:
    """경매 정산정보를 auction_settlement 테이블에 upsert."""
    if not records:
        return 0

    def _n(val):
        try:
            if val is None or str(val).strip() in ("", "-"):
                return None
            return float(str(val).replace(",", ""))
        except Exception:
            return None

    rows = [
        {
            "trd_clcln_ymd": r.get("trd_clcln_ymd"),
            "whsl_mrkt_cd":  r.get("whsl_mrkt_cd"),
            "whsl_mrkt_nm":  r.get("whsl_mrkt_nm"),
            "corp_cd":       r.get("corp_cd"),
            "corp_nm":       r.get("corp_nm"),
            "trd_se":        r.get("trd_se"),
            "gds_lclsf_cd":  r.get("gds_lclsf_cd"),
            "gds_lclsf_nm":  r.get("gds_lclsf_nm"),
            "gds_mclsf_cd":  r.get("gds_mclsf_cd"),
            "gds_mclsf_nm":  r.get("gds_mclsf_nm"),
            "gds_sclsf_cd":  r.get("gds_sclsf_cd"),
            "gds_sclsf_nm":  r.get("gds_sclsf_nm"),
            "unit_cd":       r.get("unit_cd"),
            "unit_nm":       r.get("unit_nm"),
            "unit_qty":      _n(r.get("unit_qty")),
            "pkg_cd":        r.get("pkg_cd"),
            "pkg_nm":        r.get("pkg_nm"),
            "sz_cd":         r.get("sz_cd"),
            "sz_nm":         r.get("sz_nm"),
            "grd_cd":        r.get("grd_cd"),
            "grd_nm":        r.get("grd_nm"),
            "plor_cd":       r.get("plor_cd"),
            "plor_nm":       r.get("plor_nm"),
            "unit_tot_qty":  _n(r.get("unit_tot_qty")),
            "totprc":        _n(r.get("totprc")),
            "avgprc":        _n(r.get("avgprc")),
        }
        for r in records
        if r.get("trd_clcln_ymd") and r.get("whsl_mrkt_cd")
    ]
    if not rows:
        return 0
    # 배치 내 중복 제거
    seen = {}
    for row in rows:
        key = (row["trd_clcln_ymd"], row["whsl_mrkt_cd"], row.get("corp_cd"),
               row.get("gds_lclsf_cd"), row.get("gds_mclsf_cd"), row.get("gds_sclsf_cd"),
               row.get("unit_cd"), row.get("pkg_cd"), row.get("sz_cd"),
               row.get("grd_cd"), row.get("plor_cd"), row.get("trd_se"))
        seen[key] = row
    rows = list(seen.values())
    resp = (
        _client()
        .table("auction_settlement")
        .upsert(rows, on_conflict="trd_clcln_ymd,whsl_mrkt_cd,corp_cd,gds_lclsf_cd,gds_mclsf_cd,gds_sclsf_cd,unit_cd,pkg_cd,sz_cd,grd_cd,plor_cd,trd_se")
        .execute()
    )
    return len(resp.data) if resp.data else 0


def save_shipment_sequel(records: list[dict]) -> int:
    """출하량 추이 정보를 shipment_sequel 테이블에 upsert."""
    if not records:
        return 0

    def _n(val):
        try:
            if val is None or str(val).strip() in ("", "-"):
                return None
            return float(str(val).replace(",", ""))
        except Exception:
            return None

    rows = [
        {
            "spmt_ymd":          r.get("spmt_ymd"),
            "whsl_mrkt_cd":      r.get("whsl_mrkt_cd"),
            "whsl_mrkt_nm":      r.get("whsl_mrkt_nm"),
            "corp_cd":           r.get("corp_cd"),
            "corp_nm":           r.get("corp_nm"),
            "gds_lclsf_cd":      r.get("gds_lclsf_cd"),
            "gds_lclsf_nm":      r.get("gds_lclsf_nm"),
            "gds_mclsf_cd":      r.get("gds_mclsf_cd"),
            "gds_mclsf_nm":      r.get("gds_mclsf_nm"),
            "gds_sclsf_cd":      r.get("gds_sclsf_cd"),
            "gds_sclsf_nm":      r.get("gds_sclsf_nm"),
            "unit_cd":           r.get("unit_cd"),
            "unit_nm":           r.get("unit_nm"),
            "unit_qty":          _n(r.get("unit_qty")),
            "avg_spmt_qty":      _n(r.get("avg_spmt_qty")),
            "avg_spmt_amt":      _n(r.get("avg_spmt_amt")),
            "ww1_avg_spmt_qty":  _n(r.get("ww1_bfr_avg_spmt_qty")),
            "ww1_avg_spmt_amt":  _n(r.get("ww1_bfr_avg_spmt_amt")),
            "ww2_avg_spmt_qty":  _n(r.get("ww2_bfr_avg_spmt_qty")),
            "ww2_avg_spmt_amt":  _n(r.get("ww2_bfr_avg_spmt_amt")),
            "ww3_avg_spmt_qty":  _n(r.get("ww3_bfr_avg_spmt_qty")),
            "ww3_avg_spmt_amt":  _n(r.get("ww3_bfr_avg_spmt_amt")),
            "ww4_avg_spmt_qty":  _n(r.get("ww4_bfr_avg_spmt_qty")),
            "ww4_avg_spmt_amt":  _n(r.get("ww4_bfr_avg_spmt_amt")),
        }
        for r in records
        if r.get("spmt_ymd") and r.get("whsl_mrkt_cd")
    ]
    if not rows:
        return 0
    # 배치 내 중복 제거 (ON CONFLICT DO UPDATE 에러 방지)
    seen = {}
    for row in rows:
        key = (row["spmt_ymd"], row["whsl_mrkt_cd"], row.get("corp_cd"),
               row.get("gds_lclsf_cd"), row.get("gds_mclsf_cd"), row.get("gds_sclsf_cd"))
        seen[key] = row
    rows = list(seen.values())
    resp = (
        _client()
        .table("shipment_sequel")
        .upsert(rows, on_conflict="spmt_ymd,whsl_mrkt_cd,corp_cd,gds_lclsf_cd,gds_mclsf_cd,gds_sclsf_cd")
        .execute()
    )
    return len(resp.data) if resp.data else 0


def query_price_series(crop_name: str, market_code: str, days: int = 730) -> pd.DataFrame:
    """
    price_history에서 가격 시계열 조회.

    Returns: DataFrame(index=date, columns=[price_per_kg])
    """
    start = str(date.today() - timedelta(days=days))
    resp = (
        _client()
        .table("price_history")
        .select("data_date, price_per_kg")
        .eq("crop_name", crop_name)
        .eq("market_code", market_code)
        .gte("data_date", start)
        .order("data_date")
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=["price_per_kg"])

    df = pd.DataFrame(resp.data)
    df["data_date"] = pd.to_datetime(df["data_date"])
    df = df.set_index("data_date").sort_index()
    return df
