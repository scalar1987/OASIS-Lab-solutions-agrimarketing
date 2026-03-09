"""
collector/collect_auction_settlement.py
KAT Settlement (daily aggregates) -> fetch scaffold
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

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/B552845/katSale/trades"
API_KEY = os.environ["KAMIS_API_KEY"]

INFLUX_URL = os.environ.get("INFLUXDB_URL")
INFLUX_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUX_ORG = os.environ.get("INFLUXDB_ORG")
INFLUX_BUCKET = os.environ.get("INFLUXDB_BUCKET")


def _format_date_ymd(d: date | str) -> str:
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    if "-" in d:
        datetime.strptime(d, "%Y-%m-%d")
        return d
    raise ValueError(f"Invalid date: {d}")


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


def write_to_influx(write_api, items: list[dict]):
    if not write_api:
        return
    points = []
    for item in items:
        date_str = item.get("trd_clcln_ymd")
        if not date_str:
            continue
        volume_qty = _parse_num(item.get("unit_tot_qty"))
        volume_amt = _parse_num(item.get("totprc"))
        avg_price = _parse_num(item.get("avgprc"))
        crop_name = item.get("gds_sclsf_nm") or item.get("gds_mclsf_nm") or item.get("gds_lclsf_nm")

        if volume_qty is None and volume_amt is None and avg_price is None:
            continue

        p = (
            Point("kamis_volume")
            .tag("crop_name", crop_name or "UNKNOWN")
            .tag("market_code", item.get("whsl_mrkt_cd", ""))
            .tag("market_name", item.get("whsl_mrkt_nm", ""))
            .tag("source", "auction_settlement")
            .field("volume_qty", volume_qty or 0.0)
            .field("volume_amt", volume_amt or 0.0)
            .field("avg_price", avg_price or 0.0)
            .time(date_str + "T00:00:00+09:00", WritePrecision.S)
        )
        points.append(p)

    if points:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        log.info(f"  -> InfluxDB wrote {len(points)} points")


def fetch_settlement(trd_clcln_ymd: str, whsl_mrkt_cd: str, page_no: int = 1, num_rows: int = 1000) -> dict:
    params = {
        "serviceKey": API_KEY,
        "returnType": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[trd_clcln_ymd::EQ]": trd_clcln_ymd,
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def iter_settlement_items(trd_clcln_ymd: str, whsl_mrkt_cd: str):
    page_no = 1
    while True:
        data = fetch_settlement(trd_clcln_ymd, whsl_mrkt_cd, page_no=page_no)
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        for item in items:
            yield item
        total = body.get("totalCount", 0)
        num_rows = body.get("numOfRows", len(items))
        if page_no * int(num_rows) >= int(total):
            break
        page_no += 1
        time.sleep(0.2)


def write_to_postgres(items: list[dict]):
    """
    TODO: implement PostgreSQL upsert.
    Suggested unique key: (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, gds_lclsf_cd,
    gds_mclsf_cd, gds_sclsf_cd, unit_cd, pkg_cd, sz_cd, grd_cd, plor_cd, trd_se)
    """
    log.info(f"[dry-run] would write {len(items)} rows to PostgreSQL")


def main():
    parser = argparse.ArgumentParser(description="KAT Settlement collector (scaffold)")
    parser.add_argument("--date", type=str, help="trade settlement date (YYYY-MM-DD)")
    parser.add_argument("--market", type=str, required=True, help="wholesale market code")
    parser.add_argument("--backfill", type=int, help="backfill N days including today")
    args = parser.parse_args()

    if args.backfill:
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(args.backfill, -1, -1)]
    else:
        target = args.date or str(date.today() - timedelta(days=1))
        dates = [datetime.strptime(target, "%Y-%m-%d").date()]

    write_api = None
    if INFLUX_URL and INFLUX_TOKEN and INFLUX_ORG and INFLUX_BUCKET:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
    else:
        client = None

    for d in dates:
        ymd = _format_date_ymd(d)
        log.info(f"Collecting settlement: {ymd} / market={args.market}")
        batch = list(iter_settlement_items(ymd, args.market))
        log.info(f"Fetched {len(batch)} items")
        if batch:
            write_to_postgres(batch)
            write_to_influx(write_api, batch)

    if client:
        client.close()


if __name__ == "__main__":
    main()
