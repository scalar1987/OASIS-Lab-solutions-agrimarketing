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
    perDay API 원시 데이터를 price_history 테이블에 upsert (전체 컬럼).
    Returns: upsert된 행 수
    """
    if not records:
        return 0

    def _to_date(val):
        if not val:
            return None
        s = str(val).strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        return s

    def _n(val):
        if val is None:
            return None
        try:
            return float(str(val).replace(",", ""))
        except Exception:
            return None

    rows = []
    for r in records:
        exmn_ymd = _to_date(r.get("exmn_ymd")) or r.get("date_str")
        item_cd = r.get("item_cd")
        mrkt_cd = r.get("mrkt_cd")
        if not exmn_ymd or not item_cd or not mrkt_cd:
            continue
        rows.append({
            "exmn_ymd":         exmn_ymd,
            "se_cd":            r.get("se_cd"),
            "se_nm":            r.get("se_nm"),
            "ctgry_cd":         r.get("ctgry_cd"),
            "ctgry_nm":         r.get("ctgry_nm"),
            "item_cd":          item_cd,
            "item_nm":          r.get("item_nm"),
            "vrty_cd":          r.get("vrty_cd"),
            "vrty_nm":          r.get("vrty_nm"),
            "grd_cd":           r.get("grd_cd"),
            "grd_nm":           r.get("grd_nm"),
            "sigungu_cd":       r.get("sigungu_cd"),
            "sigungu_nm":       r.get("sigungu_nm"),
            "unit":             r.get("unit"),
            "unit_sz":          r.get("unit_sz"),
            "mrkt_cd":          mrkt_cd,
            "mrkt_nm":          r.get("mrkt_nm"),
            "exmn_dd_prc":      _n(r.get("exmn_dd_prc")),
            "exmn_dd_cnvs_prc": _n(r.get("exmn_dd_cnvs_prc")),
            "orgn_rgstr_dt":    r.get("orgn_rgstr_dt"),
            "crop_name":        r.get("crop_name"),
        })

    if not rows:
        return 0

    # 배치 내 중복 제거
    seen = {}
    for row in rows:
        key = (row["exmn_ymd"], row.get("se_cd"), row["item_cd"],
               row.get("vrty_cd"), row.get("grd_cd"), row["mrkt_cd"])
        seen[key] = row
    rows = list(seen.values())

    total = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        resp = (
            _client()
            .table("price_history")
            .upsert(chunk, on_conflict="exmn_ymd,se_cd,item_cd,vrty_cd,grd_cd,mrkt_cd")
            .execute()
        )
        total += len(resp.data) if resp.data else 0
    return total


def save_kosis_stats(records: list[dict]) -> int:
    """
    KOSIS 재배면적/생산량 통계를 crop_area_stats 테이블에 upsert.
    Returns: upsert된 행 수
    """
    if not records:
        return 0

    rows = [
        {
            "year":               r.get("year"),
            "crop_name":          r.get("crop_name"),
            "region_cd":          r.get("region_cd", "00"),
            "region_nm":          r.get("region_nm", "전국"),
            "cultivation_area_ha": r.get("cultivation_area_ha"),
            "harvest_area_ha":    r.get("harvest_area_ha"),
            "production_ton":     r.get("production_ton"),
            "yield_per_10a":      r.get("yield_per_10a"),
            "source":             r.get("source", "KOSIS"),
        }
        for r in records
        if r.get("year") and r.get("crop_name")
    ]
    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        resp = (
            _client()
            .table("crop_area_stats")
            .upsert(chunk, on_conflict="year,crop_name,region_cd")
            .execute()
        )
        total += len(resp.data) if resp.data else 0
    return total


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
            "se_cd":            r.get("se_cd"),
            "se_nm":            r.get("se_nm"),
            "ctgry_cd":         r.get("ctgry_cd"),
            "ctgry_nm":         r.get("ctgry_nm"),
            "item_cd":          r.get("item_cd"),
            "item_nm":          r.get("item_nm"),
            "vrty_cd":          r.get("vrty_cd"),
            "vrty_nm":          r.get("vrty_nm"),
            "grd_cd":           r.get("grd_cd"),
            "grd_nm":           r.get("grd_nm"),
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
    # 배치 내 중복 제거 (ON CONFLICT DO UPDATE 에러 방지)
    seen = {}
    for row in rows:
        key = (row["trd_clcln_ymd"], row["whsl_mrkt_cd"], row.get("corp_cd"),
               row.get("spm_no"), row.get("auctn_seq"), row.get("auctn_seq2"))
        seen[key] = row
    rows = list(seen.values())
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


def save_krei_outlook(records: list[dict]) -> int:
    """
    KREI 농업관측월보 파싱 결과를 krei_outlook 테이블에 upsert.
    Returns: upsert된 행 수
    """
    if not records:
        return 0

    def _n(val):
        try:
            if val is None:
                return None
            return float(val)
        except (ValueError, TypeError):
            return None

    rows = [
        {
            "year_month":              r.get("year_month"),
            "report_category":         r.get("report_category", ""),
            "crop_name":               r.get("crop_name"),
            "price_unit":              r.get("price_unit"),
            "prev_month_price":        _n(r.get("prev_month_price")),
            "prev_month_vs_prev_year": r.get("prev_month_vs_prev_year"),
            "shipment_chg_pct":        _n(r.get("shipment_chg_pct")),
            "shipment_direction":      r.get("shipment_direction"),
            "cultivation_area_ha":     _n(r.get("cultivation_area_ha")),
            "yield_per_10a":           _n(r.get("yield_per_10a")),
            "production_ton":          _n(r.get("production_ton")),
            "forecast_price":          _n(r.get("forecast_price")),
            "forecast_vs_prev_year":   r.get("forecast_vs_prev_year"),
            "source_url":              r.get("source_url"),
        }
        for r in records
        if r.get("year_month") and r.get("crop_name")
    ]
    if not rows:
        return 0

    resp = (
        _client()
        .table("krei_outlook")
        .upsert(rows, on_conflict="year_month,crop_name")
        .execute()
    )
    return len(resp.data) if resp.data else 0


def query_price_series(crop_name: str, market_code: str, days: int = 730,
                       grd_cd: str = "04") -> pd.DataFrame:
    """
    price_history에서 가격 시계열 조회.
    grd_cd: 등급코드 (기본 "04"=상품). None이면 전체 등급.

    Returns: DataFrame(index=date, columns=[exmn_dd_cnvs_prc])
    """
    start = str(date.today() - timedelta(days=days))
    q = (
        _client()
        .table("price_history")
        .select("exmn_ymd, exmn_dd_cnvs_prc, grd_cd, grd_nm")
        .eq("crop_name", crop_name)
        .eq("mrkt_cd", market_code)
        .gte("exmn_ymd", start)
        .order("exmn_ymd")
    )
    if grd_cd:
        q = q.eq("grd_cd", grd_cd)
    resp = q.execute()
    if not resp.data:
        return pd.DataFrame(columns=["exmn_dd_cnvs_prc"])

    df = pd.DataFrame(resp.data)
    df["exmn_ymd"] = pd.to_datetime(df["exmn_ymd"])
    df = df.set_index("exmn_ymd").sort_index()
    # 하위 호환: price_per_kg 컬럼 별칭
    df["price_per_kg"] = df["exmn_dd_cnvs_prc"]
    return df
