"""
collect_rises_falls.py
KAMIS 가격 등락 정보 API (전국 평균 + 등락율) -> Supabase

Run:
  python collect_rises_falls.py                     # today
  python collect_rises_falls.py --date 2026-03-09   # single date
  python collect_rises_falls.py --backfill 365      # backfill N days
  python collect_rises_falls.py --from-date 2025-01-01 --to-date 2026-03-08
"""

import os
import time
import argparse
import logging
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv
from db.supabase_client import save_rises_falls

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RISES_FALLS_BASE = "https://apis.data.go.kr/B552845/risesAndFalls/info"
KAMIS_API_KEY = os.environ["KAMIS_API_KEY"]

SE_CODE    = "02"   # 02: 중도매
GRADE_CODE = "04"   # 04: 상품

# (crop_name, ctgry_cd, item_cd, vrty_cd)  vrty_cd=None → 전체 품종
CROPS = [
    ("양파",    "200", "245", "00"),
    ("배추",    "200", "211", None),
    ("무",      "200", "231", None),
    ("마늘",    "200", "244", None),
    ("감자",    "100", "152", "01"),   # 수미(노지)
    ("고추",    "200", "243", "00"),   # 붉은고추
    ("대파",    "200", "246", "00"),
    ("사과",    "400", "411", "05"),   # 후지
    ("배",      "400", "412", "01"),   # 신고
    ("파프리카", "200", "256", "00"),
    ("피망",    "200", "255", "00"),
]


def _safe_float(val) -> float | None:
    try:
        if val is None or str(val).strip() == "":
            return None
        return float(str(val).replace(",", ""))
    except Exception:
        return None


def fetch_rises_falls(exmn_ymd: str, ctgry_cd: str, item_cd: str, vrty_cd: str | None) -> list[dict]:
    params = {
        "serviceKey":          KAMIS_API_KEY,
        "returnType":          "json",
        "pageNo":              1,
        "numOfRows":           100,
        "cond[exmn_ymd::EQ]":  exmn_ymd,
        "cond[se_cd::EQ]":     SE_CODE,
        "cond[ctgry_cd::EQ]":  ctgry_cd,
        "cond[item_cd::EQ]":   item_cd,
        "cond[grd_cd::EQ]":    GRADE_CODE,
    }
    if vrty_cd:
        params["cond[vrty_cd::EQ]"] = vrty_cd

    try:
        resp = requests.get(RISES_FALLS_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("response", {}).get("body", {}).get("items", {})
        if not items:
            return []
        item_list = items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
        return item_list
    except Exception as e:
        log.warning(f"Fetch failed [{item_cd}/{vrty_cd}/{exmn_ymd}]: {e}")
        return []


def collect_for_date(target_date: str) -> int:
    exmn_ymd = target_date.replace("-", "")
    records = []

    for crop_name, ctgry_cd, item_cd, vrty_cd in CROPS:
        items = fetch_rises_falls(exmn_ymd, ctgry_cd, item_cd, vrty_cd)
        for item in items:
            avg_price_per_kg = _safe_float(item.get("exmn_dd_cnvs_avg_prc"))
            if not avg_price_per_kg:
                continue
            dd1 = _safe_float(item.get("dd1_bfr_cmpr_rafrt"))
            ww1 = _safe_float(item.get("ww1_bfr_cmpr_rafrt"))
            mm1 = _safe_float(item.get("mm1_bfr_cmpr_rafrt"))
            records.append({
                "data_date":        target_date,
                "crop_name":        crop_name,
                "ctgry_cd":         item.get("ctgry_cd"),
                "item_cd":          item.get("item_cd"),
                "vrty_cd":          item.get("vrty_cd"),
                "vrty_nm":          item.get("vrty_nm"),
                "grd_cd":           item.get("grd_cd"),
                "se_cd":            item.get("se_cd"),
                "unit":             item.get("unit"),
                "unit_sz":          item.get("unit_sz"),
                "avg_price":        _safe_float(item.get("exmn_dd_avg_prc")),
                "avg_price_per_kg": avg_price_per_kg,
                "dd1_change_rate":  dd1,
                "ww1_change_rate":  ww1,
                "mm1_change_rate":  mm1,
                "yy1_change_rate":  _safe_float(item.get("yy1_bfr_cmpr_rafrt")),
            })
            log.info(
                f"  [{crop_name}/{item.get('vrty_nm','-')}] "
                f"{avg_price_per_kg:,.0f}원/kg | "
                f"1일:{dd1}% 1주:{ww1}% 1월:{mm1}%"
            )
        time.sleep(0.1)

    if records:
        n = save_rises_falls(records)
        log.info(f"  -> Supabase upserted {n} rows")

    return len(records)


def main():
    parser = argparse.ArgumentParser(description="KAMIS 가격 등락 정보 수집기")
    parser.add_argument("--date",      type=str, help="target date (YYYY-MM-DD)")
    parser.add_argument("--backfill",  type=int, help="backfill N days ending today")
    parser.add_argument("--from-date", type=str, dest="from_date", help="range start (YYYY-MM-DD)")
    parser.add_argument("--to-date",   type=str, dest="to_date",   help="range end (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.from_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
        end   = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else date.today()
        days  = (end - start).days + 1
        dates = [str(start + timedelta(days=i)) for i in range(days)]
        log.info(f"Range backfill: {dates[0]} ~ {dates[-1]} ({len(dates)} days)")
        total = 0
        for d in dates:
            log.info(f"-- Collect {d} --")
            total += collect_for_date(d)
            time.sleep(0.5)
        log.info(f"Range backfill done: {total} records")

    elif args.backfill:
        today = date.today()
        dates = [str(today - timedelta(days=i)) for i in range(args.backfill, -1, -1)]
        log.info(f"Backfill: {dates[0]} ~ {dates[-1]} ({len(dates)} days)")
        total = 0
        for d in dates:
            log.info(f"-- Collect {d} --")
            total += collect_for_date(d)
            time.sleep(0.5)
        log.info(f"Backfill done: {total} records")

    else:
        target = args.date or str(date.today())
        log.info(f"-- Collect {target} --")
        count = collect_for_date(target)
        log.info(f"Done: {count} records")


if __name__ == "__main__":
    main()
