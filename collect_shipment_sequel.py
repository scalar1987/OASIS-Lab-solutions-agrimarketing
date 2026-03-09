"""
collector/collect_shipment_sequel.py
Shipment sequel (weekly averages) -> fetch scaffold
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
from db.supabase_client import save_shipment_sequel

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/B552845/shipmentSequel/info"
API_KEY = os.environ["KAMIS_API_KEY"]

INFLUX_URL = os.environ.get("INFLUXDB_URL")
INFLUX_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUX_ORG = os.environ.get("INFLUXDB_ORG")
INFLUX_BUCKET = os.environ.get("INFLUXDB_BUCKET")


def _format_date_yyyymmdd(d: date | str) -> str:
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    if "-" in d:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")
    if len(d) == 8 and d.isdigit():
        return d
    raise ValueError(f"Invalid date: {d}")


def _format_iso_date(yyyymmdd: str) -> str:
    return datetime.strptime(yyyymmdd, "%Y%m%d").strftime("%Y-%m-%d")


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


def write_to_influx(write_api, items: list[dict], spmt_ymd: str):
    if not write_api:
        return
    points = []
    date_str = _format_iso_date(spmt_ymd)
    for item in items:
        volume_qty = _parse_num(item.get("avg_spmt_qty"))
        volume_amt = _parse_num(item.get("avg_spmt_amt"))
        crop_name = item.get("gds_sclsf_nm") or item.get("gds_mclsf_nm") or item.get("gds_lclsf_nm")

        if volume_qty is None and volume_amt is None:
            continue

        p = (
            Point("kamis_volume")
            .tag("crop_name", crop_name or "UNKNOWN")
            .tag("market_code", item.get("whsl_mrkt_cd", ""))
            .tag("market_name", item.get("whsl_mrkt_nm", ""))
            .tag("source", "shipment_sequel")
            .field("volume_qty", volume_qty or 0.0)
            .field("volume_amt", volume_amt or 0.0)
            .field("avg_price", 0.0)
            .time(date_str + "T00:00:00+09:00", WritePrecision.S)
        )
        points.append(p)

    if points:
        try:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
            log.info(f"  -> InfluxDB wrote {len(points)} points")
        except Exception as e:
            log.warning(f"  -> InfluxDB write skipped (retention?): {e}")


def fetch_sequel(spmt_ymd: str, whsl_mrkt_cd: str | None, page_no: int = 1, num_rows: int = 1000) -> dict:
    params = {
        "serviceKey": API_KEY,
        "returnType": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
        "cond[spmt_ymd::EQ]": spmt_ymd,
    }
    if whsl_mrkt_cd:
        params["cond[whsl_mrkt_cd::EQ]"] = whsl_mrkt_cd

    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def iter_sequel_items(spmt_ymd: str, whsl_mrkt_cd: str | None):
    page_no = 1
    while True:
        data = fetch_sequel(spmt_ymd, whsl_mrkt_cd, page_no=page_no)
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


def write_to_postgres(items: list[dict], spmt_ymd: str):
    # spmt_ymd를 각 record에 주입 (API 응답에 없을 경우 대비)
    for item in items:
        if not item.get("spmt_ymd"):
            item["spmt_ymd"] = _format_iso_date(spmt_ymd)
    n = save_shipment_sequel(items)
    log.info(f"  -> Supabase upserted {n} rows")


def main():
    parser = argparse.ArgumentParser(description="Shipment sequel collector (scaffold)")
    parser.add_argument("--date", type=str, help="shipment date (YYYY-MM-DD or YYYYMMDD)")
    parser.add_argument("--market", type=str, help="wholesale market code")
    parser.add_argument("--backfill", type=int, help="backfill N days including today")
    parser.add_argument("--from-date", type=str, dest="from_date", help="range start (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, dest="to_date", help="range end (YYYY-MM-DD, inclusive)")
    args = parser.parse_args()

    if args.from_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
        end   = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else date.today()
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    elif args.backfill:
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
        ymd = _format_date_yyyymmdd(d)
        log.info(f"Collecting shipment sequel: {ymd} / market={args.market or 'ALL'}")
        batch = list(iter_sequel_items(ymd, args.market))
        log.info(f"Fetched {len(batch)} items")
        if batch:
            write_to_postgres(batch, ymd)
            write_to_influx(write_api, batch, ymd)

    if client:
        client.close()


if __name__ == "__main__":
    main()
