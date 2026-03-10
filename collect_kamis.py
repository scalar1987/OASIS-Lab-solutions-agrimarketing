"""
collector/collect_kamis.py
KAMIS per-day price API -> InfluxDB Cloud

Run:
  python collect_kamis.py                    # today (local date)
  python collect_kamis.py --date 2026-03-09  # single date (YYYY-MM-DD)
  python collect_kamis.py --backfill 365     # backfill N days
"""

import os
import time
import argparse
import logging
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from db.supabase_client import save_price_history

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KAMIS_BASE = "https://apis.data.go.kr/B552845/perDay/price"
KAT_SALE_BASE = "https://apis.data.go.kr/B552845/katSale/trades"
KAMIS_API_KEY = os.environ["KAMIS_API_KEY"]

INFLUX_URL = os.environ["INFLUXDB_URL"]
INFLUX_TOKEN = os.environ["INFLUXDB_TOKEN"]
INFLUX_ORG = os.environ["INFLUXDB_ORG"]
INFLUX_BUCKET = os.environ["INFLUXDB_BUCKET"]

SE_CODE = "02"   # 01: retail, 02: wholesale

# (crop_name, ctgry_cd, item_cd, vrty_cd)
DEFAULT_CROPS = [
    ("양파", "200", "245", None),
    ("배추", "200", "211", None),
    ("무", "200", "231", None),
    ("마늘", "200", "244", None),
    ("감자", "100", "152", None),
    ("고추", "200", "243", None),
    ("대파", "200", "246", None),
    ("사과", "400", "411", None),
    ("배", "400", "412", None),
    ("파프리카", "200", "256", None),
    ("피망", "200", "255", None),
]

# 일별 도소매 가격정보 API에서 수집 가능한 공영도매시장 (perDay 시장코드 기준)
# 코드 없는 시장(강서, 반여, 인천, 노은, 안양, 안산, 구리, 원주, 천안, 익산, 정읍, 순천, 안동, 구미, 창원, 진주 등)은 API 미지원
# (시장명, perDay 시장코드, katSale whsl_mrkt_cd)
MARKETS = [
    # 서울
    ("서울가락",  "0110211", None),   # 가락도매
    # 부산
    ("부산엄궁",  "0210042", None),   # 엄궁도매
    # 대구
    ("대구북부",  "0220021", None),   # 북부도매
    # 광주
    ("광주각화",  "0240122", None),   # 각화도매
    ("광주서부",  "0240123", None),   # 서부도매
    # 대전
    ("대전오정",  "0250113", None),   # 오정도매
    # 울산
    ("울산",      "0260100", None),   # 울산
    # 경기
    ("수원",      "0311100", None),   # 수원
    # 강원
    ("춘천",      "0321100", None),   # 춘천
    ("강릉",      "0321400", None),   # 강릉
    # 충북
    ("청주",      "0331100", None),   # 청주
    ("충주",      "0331200", None),   # 충주
    # 전북
    ("전주",      "0351100", None),   # 전주
    # 경북
    ("포항",      "0370001", None),   # 죽도(포항)
]


def _format_yyyymmdd(d: date | str) -> str:
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    if "-" in d:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")
    if len(d) == 8 and d.isdigit():
        return d
    raise ValueError(f"Invalid date format: {d}")


def _format_iso_date(yyyymmdd: str) -> str:
    return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")


def _parse_price(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("-", "0")
    try:
        num = float(cleaned)
    except ValueError:
        return None
    return num if num > 0 else None


def _parse_num(value: str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(",", "").replace("-", "0")
    try:
        num = float(cleaned)
    except ValueError:
        return None
    return num if num > 0 else None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value if ch.isalnum()).lower()


def _match_market_name(item_market: str | None, target_market: str) -> bool:
    item_norm = _normalize_text(item_market)
    target_norm = _normalize_text(target_market)
    if not item_norm or not target_norm:
        return False
    return target_norm in item_norm or item_norm in target_norm


def _match_crop_name(item_crop: str | None, target_crop: str) -> bool:
    item_norm = _normalize_text(item_crop)
    target_norm = _normalize_text(target_crop)
    if not item_norm or not target_norm:
        return False
    return target_norm in item_norm or item_norm in target_norm


def fetch_kat_sale_items(trd_clcln_ymd: str, whsl_mrkt_cd: str) -> list[dict]:
    page_no = 1
    items_all = []
    selectable = ",".join([
        "whsl_mrkt_cd",
        "whsl_mrkt_nm",
        "trd_clcln_ymd",
        "gds_lclsf_nm",
        "gds_mclsf_nm",
        "gds_sclsf_nm",
        "avgprc",
        "unit_qty",
        "unit_cd",
        "unit_tot_qty",
    ])
    while True:
        params = {
            "serviceKey": KAMIS_API_KEY,
            "returnType": "json",
            "pageNo": str(page_no),
            "numOfRows": "1000",
            "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
            "cond[trd_clcln_ymd::EQ]": trd_clcln_ymd,
            "selectable": selectable,
        }
        try:
            resp = requests.get(KAT_SALE_BASE, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"katSale fetch failed [{whsl_mrkt_cd}/{trd_clcln_ymd}]: {e}")
            break

        header = data.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        if result_code not in ("00", "0", None):
            log.warning(f"katSale error {result_code}: {header.get('resultMsg')}")
            break

        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        items_all.extend(items)

        total = body.get("totalCount", 0)
        num_rows = int(body.get("numOfRows", len(items)))
        if page_no * num_rows >= int(total):
            break
        page_no += 1
        time.sleep(0.1)

    return items_all


def extract_kat_sale_price(items: list[dict], market_name: str, crop_name: str) -> dict | None:
    weight_sum = 0.0
    weighted_price_sum = 0.0
    price_sum = 0.0
    price_count = 0
    volume_kg = 0.0

    for item in items:
        if not _match_market_name(item.get("whsl_mrkt_nm"), market_name):
            continue
        crop_nm = (
            item.get("gds_sclsf_nm")
            or item.get("gds_mclsf_nm")
            or item.get("gds_lclsf_nm")
        )
        if not _match_crop_name(crop_nm, crop_name):
            continue
        avgprc = _parse_num(item.get("avgprc"))
        unit_qty = _parse_num(item.get("unit_qty"))
        unit_tot_qty = _parse_num(item.get("unit_tot_qty"))
        if not avgprc or not unit_qty or unit_qty <= 0:
            continue
        price_per_kg = avgprc / unit_qty
        if unit_tot_qty and unit_tot_qty > 0:
            vol = unit_tot_qty * unit_qty
            weighted_price_sum += price_per_kg * vol
            weight_sum += vol
            volume_kg += vol
        else:
            price_sum += price_per_kg
            price_count += 1

    if weight_sum > 0:
        price = weighted_price_sum / weight_sum
    elif price_count > 0:
        price = price_sum / price_count
    else:
        return None

    return {"price_per_kg": price, "volume_kg": volume_kg}


def fetch_daily_prices(ctgry_cd: str, item_cd: str, vrty_cd: str | None, mrkt_cd: str, exmn_ymd: str) -> list[dict]:
    """perDay API에서 해당 날짜/품목/시장의 전체 등급 항목을 반환."""
    params = {
        "serviceKey": KAMIS_API_KEY,
        "returnType": "json",
        "pageNo": "1",
        "numOfRows": "1000",
        "cond[exmn_ymd::GTE]": exmn_ymd,
        "cond[exmn_ymd::LTE]": exmn_ymd,
        "cond[ctgry_cd::EQ]": ctgry_cd,
        "cond[item_cd::EQ]": item_cd,
        "cond[se_cd::EQ]": SE_CODE,
        "cond[mrkt_cd::EQ]": mrkt_cd,
    }
    if vrty_cd:
        params["cond[vrty_cd::EQ]"] = vrty_cd

    try:
        resp = requests.get(KAMIS_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        header = data.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        if result_code not in ("00", "0", None):
            log.warning(f"KAMIS error {result_code}: {header.get('resultMsg')}")
            return []

        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items or []

    except Exception as e:
        log.warning(f"KAMIS fetch failed [{item_cd}/{mrkt_cd}/{exmn_ymd}]: {e}")
        return []


def write_to_influx(write_api, records: list[dict]):
    points = []
    for r in records:
        price = r.get("exmn_dd_cnvs_prc") or r.get("price_per_kg")
        if not price:
            continue
        p_price = (
            Point("kamis_price")
            .tag("crop_name", r.get("crop_name", ""))
            .tag("market_code", r.get("mrkt_cd") or r.get("market_code", ""))
            .tag("market_name", r.get("mrkt_nm") or r.get("market_name", ""))
            .tag("grade_cd", r.get("grd_cd", ""))
            .tag("grade_nm", r.get("grd_nm", ""))
            .tag("vrty_nm", r.get("vrty_nm", ""))
            .field("price_per_kg", float(price))
            .time(r["date_str"] + "T00:00:00+09:00", WritePrecision.S)
        )
        points.append(p_price)

    if points:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        log.info(f"  -> InfluxDB wrote {len(points)} points")


def collect_for_date(target_date: str, write_api) -> int:
    records = []
    exmn_ymd = _format_yyyymmdd(target_date)
    date_str = _format_iso_date(exmn_ymd)
    kat_sale_cache: dict[str, list[dict]] = {}
    crops = [
        {"crop_name": c[0], "ctgry_cd": c[1], "item_cd": c[2], "vrty_cd": c[3]}
        for c in DEFAULT_CROPS
    ]

    for crop in crops:
        crop_name = crop["crop_name"]
        ctgry_cd = crop["ctgry_cd"]
        item_cd = crop["item_cd"]
        vrty_cd = crop.get("vrty_cd")
        for market_name, perday_code, katsale_code in MARKETS:
            if perday_code:
                items = fetch_daily_prices(ctgry_cd, item_cd, vrty_cd, perday_code, exmn_ymd)
                for item in items:
                    price = _parse_price(item.get("exmn_dd_cnvs_prc")) or _parse_price(item.get("exmn_dd_prc"))
                    if price is None:
                        continue
                    records.append({
                        **item,
                        "crop_name": crop_name,
                        "date_str": date_str,
                        "exmn_dd_cnvs_prc": price,
                    })
                if items:
                    grades = [i.get("grd_nm", i.get("grd_cd", "?")) for i in items if _parse_price(i.get("exmn_dd_cnvs_prc"))]
                    log.info(f"  [{crop_name}/{market_name}] {len(items)} items ({', '.join(grades)})")
                time.sleep(0.05)
                continue

            if not katsale_code:
                continue

            kat_items = kat_sale_cache.get(katsale_code)
            if kat_items is None:
                kat_items = fetch_kat_sale_items(date_str, katsale_code)
                kat_sale_cache[katsale_code] = kat_items
                time.sleep(0.05)
            result = extract_kat_sale_price(kat_items, market_name, crop_name)
            if result:
                records.append({
                    "crop_name": crop_name,
                    "mrkt_nm": market_name,
                    "mrkt_cd": katsale_code,
                    "date_str": date_str,
                    "exmn_dd_cnvs_prc": result["price_per_kg"],
                })
                log.info(
                    f"  [{crop_name}/{market_name}] {result['price_per_kg']:,.0f} won/kg (katSale)"
                )

    if records:
        try:
            write_to_influx(write_api, records)
        except Exception as e:
            log.warning(f"  -> InfluxDB write skipped (retention?): {e}")
        n = save_price_history(records)
        log.info(f"  -> Supabase upserted {n} price rows")

    return len(records)


def main():
    parser = argparse.ArgumentParser(description="KAMIS -> InfluxDB collector")
    parser.add_argument("--date", type=str, help="target date (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="backfill N days ending today")
    parser.add_argument("--from-date", type=str, dest="from_date", help="range start (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, dest="to_date", help="range end (YYYY-MM-DD, inclusive)")
    args = parser.parse_args()

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        if args.from_date:
            start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            end   = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else date.today()
            days  = (end - start).days + 1
            dates = [str(start + timedelta(days=i)) for i in range(days)]
            log.info(f"Range backfill: {dates[0]} ~ {dates[-1]} ({len(dates)} days)")
            total = 0
            for d in dates:
                log.info(f"-- Collect {d} --")
                total += collect_for_date(d, write_api)
                time.sleep(1)
            log.info(f"Range backfill done: {total} records")
        elif args.backfill:
            today = date.today()
            dates = [str(today - timedelta(days=i)) for i in range(args.backfill, -1, -1)]
            log.info(f"Backfill: {dates[0]} ~ {dates[-1]} ({len(dates)} days)")
            total = 0
            for d in dates:
                log.info(f"-- Collect {d} --")
                total += collect_for_date(d, write_api)
                time.sleep(1)
            log.info(f"Backfill done: {total} records")
        else:
            target = args.date or str(date.today())
            log.info(f"-- Collect {target} --")
            count = collect_for_date(target, write_api)
            log.info(f"Done: {count} records")
    finally:
        client.close()


if __name__ == "__main__":
    main()
