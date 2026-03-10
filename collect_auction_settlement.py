"""
collector/collect_auction_settlement.py
KAT Settlement (daily aggregates) -> fetch scaffold
"""

import os
import time
import argparse
import logging
from datetime import date, datetime, timedelta

BACKFILL_START = date(2025, 3, 9)  # 백필 시작일

import requests
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from db.supabase_client import save_auction_settlement

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
        try:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
            log.info(f"  -> InfluxDB wrote {len(points)} points")
        except Exception as e:
            log.warning(f"  -> InfluxDB write skipped (retention?): {e}")


def fetch_settlement(trd_clcln_ymd: str, whsl_mrkt_cd: str, page_no: int = 1, num_rows: int = 1000) -> dict:
    params = {
        "serviceKey": API_KEY,
        "returnType": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
        "cond[whsl_mrkt_cd::EQ]": whsl_mrkt_cd,
        "cond[trd_clcln_ymd::EQ]": trd_clcln_ymd,
    }
    for attempt in range(5):
        resp = requests.get(BASE_URL, params=params, timeout=20)
        if resp.status_code == 429:
            wait = 60 * (attempt + 1)
            log.warning(f"  429 Too Many Requests, waiting {wait}s (attempt {attempt+1}/5)")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()  # 5회 실패 시 에러 발생


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


def _get_max_collected_date(market_cd: str) -> date | None:
    """Supabase에서 해당 시장의 최신 수집 날짜 조회."""
    from db.supabase_client import _client
    resp = (
        _client()
        .table("auction_settlement")
        .select("trd_clcln_ymd")
        .eq("whsl_mrkt_cd", market_cd)
        .order("trd_clcln_ymd", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return datetime.strptime(resp.data[0]["trd_clcln_ymd"], "%Y-%m-%d").date()
    return None


def write_to_postgres(items: list[dict]):
    n = save_auction_settlement(items)
    log.info(f"  -> Supabase upserted {n} rows")


def main():
    parser = argparse.ArgumentParser(description="KAT Settlement collector (scaffold)")
    parser.add_argument("--date", type=str, help="trade settlement date (YYYY-MM-DD)")
    parser.add_argument("--market", type=str, required=True, help="wholesale market code")
    parser.add_argument("--backfill", type=int, help="backfill N days including today")
    parser.add_argument("--from-date", type=str, dest="from_date", help="range start (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, dest="to_date", help="range end (YYYY-MM-DD, inclusive)")
    parser.add_argument("--chunk-days", type=int, dest="chunk_days", default=None,
                        help="limit processing to N days from from_date (to avoid daily API quota)")
    args = parser.parse_args()

    yesterday = date.today() - timedelta(days=1)

    if args.from_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
        end   = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else date.today()
        if args.chunk_days:
            chunk_end = start + timedelta(days=args.chunk_days - 1)
            end = min(end, chunk_end)
            log.info(f"chunk-days={args.chunk_days}: processing {start} ~ {end}")
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    elif args.backfill:
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(args.backfill, -1, -1)]
    elif args.date:
        dates = [datetime.strptime(args.date, "%Y-%m-%d").date()]
    else:
        # auto-backfill 모드: Supabase 최신 날짜 기준으로 자동 진행
        max_date = _get_max_collected_date(args.market)
        if max_date is not None and max_date >= yesterday:
            log.info(f"market={args.market} already up to date (max={max_date}), collecting yesterday")
            dates = [yesterday]
        else:
            if max_date is None or max_date < BACKFILL_START:
                start = BACKFILL_START
            else:
                start = max_date + timedelta(days=1)
            chunk = args.chunk_days or 100
            end = min(yesterday, start + timedelta(days=chunk - 1))
            log.info(f"auto-backfill market={args.market}: {start} ~ {end} (chunk={chunk})")
            dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

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
