"""
collector/collect_auction_origin.py
KAT Origin (auction origin trades) -> fetch scaffold
"""

import os
import time
import argparse
import logging
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/B552845/katOrigin/trades"
API_KEY = os.environ["KAMIS_API_KEY"]


def _format_date_ymd(d: date | str) -> str:
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    if "-" in d:
        datetime.strptime(d, "%Y-%m-%d")
        return d
    raise ValueError(f"Invalid date: {d}")


def fetch_origin_trades(trd_clcln_ymd: str, whsl_mrkt_cd: str, page_no: int = 1, num_rows: int = 1000) -> dict:
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


def iter_origin_items(trd_clcln_ymd: str, whsl_mrkt_cd: str):
    page_no = 1
    while True:
        data = fetch_origin_trades(trd_clcln_ymd, whsl_mrkt_cd, page_no=page_no)
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
    Use a unique key on (trd_clcln_ymd, whsl_mrkt_cd, corp_cd, spm_no, auctn_seq, auctn_seq2).
    """
    log.info(f"[dry-run] would write {len(items)} rows to PostgreSQL")


def main():
    parser = argparse.ArgumentParser(description="KAT Origin trades collector (scaffold)")
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

    for d in dates:
        ymd = _format_date_ymd(d)
        log.info(f"Collecting origin trades: {ymd} / market={args.market}")
        batch = list(iter_origin_items(ymd, args.market))
        log.info(f"Fetched {len(batch)} items")
        if batch:
            write_to_postgres(batch)


if __name__ == "__main__":
    main()
