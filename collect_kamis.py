"""
collector/collect_kamis.py
aT KAMIS API → InfluxDB Cloud 적재

실행:
  python collect_kamis.py                    # 오늘 날짜
  python collect_kamis.py --date 2026-03-09  # 특정 날짜
  python collect_kamis.py --backfill 365     # 과거 N일 소급 수집
"""

import os
import sys
import time
import argparse
import logging
import requests
from datetime import date, timedelta
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────

KAMIS_BASE = "https://www.kamis.or.kr/service/price/xml.do"
KAMIS_API_KEY  = os.environ["KAMIS_API_KEY"]
KAMIS_CERT_KEY = os.environ.get("KAMIS_CERT_KEY", KAMIS_API_KEY)

INFLUX_URL    = os.environ["INFLUXDB_URL"]
INFLUX_TOKEN  = os.environ["INFLUXDB_TOKEN"]
INFLUX_ORG    = os.environ["INFLUXDB_ORG"]
INFLUX_BUCKET = os.environ["INFLUXDB_BUCKET"]

# 수집 대상 작목: (작목명, KAMIS 품목코드, 부류코드)
# 부류코드: 01=채소, 02=과일, 05=곡물
CROPS = [
    ("배추", "111", "01"),
    ("고추", "243", "01"),
    ("양파", "221", "01"),
    ("마늘", "231", "01"),
    ("대파", "261", "01"),
    ("감자", "152", "01"),
    ("사과", "411", "02"),
    ("배",   "412", "02"),
    ("포도", "414", "02"),
]

# 수집 대상 도매시장: (시장명, KAMIS 시장코드)
MARKETS = [
    ("가락",   "1101"),
    ("강서",   "1104"),
    ("구리",   "1302"),
    ("부산엄궁", "2100"),
    ("대구북부", "2200"),
]

GRADE_CODE = "01"  # 01=상품


# ── KAMIS API 호출 ─────────────────────────────────────────────

def fetch_daily_price(item_code: str, product_cls_code: str,
                      country_code: str, target_date: str) -> dict | None:
    """
    KAMIS 일별 소매가격 조회 (도매 + 소매 통합 엔드포인트)
    Returns: { price_per_kg, volume_kg } or None
    """
    params = {
        "action":              "dailySalesList",
        "p_cert_key":          KAMIS_CERT_KEY,
        "p_cert_id":           KAMIS_API_KEY,
        "p_returntype":        "json",
        "p_product_cls_code":  product_cls_code,
        "p_item_code":         item_code,
        "p_kind_code":         GRADE_CODE,
        "p_country_code":      country_code,
        "p_regday":            target_date,
        "p_convert_kg_yn":     "Y",
    }
    try:
        resp = requests.get(KAMIS_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # KAMIS 응답 파싱 — 구조가 버전마다 달라 방어적으로 처리
        items = (data.get("data", {})
                     .get("item", []))
        if not items:
            return None

        item = items[0]
        price_str  = item.get("dpr1", "0").replace(",", "").replace("-", "0")
        volume_str = item.get("qty", "0").replace(",", "").replace("-", "0")

        price  = float(price_str)  if price_str  else 0.0
        volume = float(volume_str) if volume_str else 0.0

        if price <= 0:
            return None

        return {"price_per_kg": price, "volume_kg": volume}

    except Exception as e:
        log.warning(f"KAMIS fetch failed [{item_code}/{country_code}/{target_date}]: {e}")
        return None


# ── InfluxDB 적재 ──────────────────────────────────────────────

def write_to_influx(write_api, records: list[dict]):
    """
    records: [
      { crop_name, market_name, market_code, date_str,
        price_per_kg, volume_kg }
    ]
    """
    points = []
    for r in records:
        # 가격 포인트
        p_price = (
            Point("kamis_price")
            .tag("crop_name",   r["crop_name"])
            .tag("market_code", r["market_code"])
            .tag("market_name", r["market_name"])
            .tag("grade",       "상품")
            .field("price_per_kg", r["price_per_kg"])
            .time(r["date_str"] + "T00:00:00+09:00", WritePrecision.SECONDS)
        )
        points.append(p_price)

        # 반입량 포인트 (volume > 0일 때만)
        if r["volume_kg"] > 0:
            p_vol = (
                Point("kamis_volume")
                .tag("crop_name",   r["crop_name"])
                .tag("market_code", r["market_code"])
                .tag("market_name", r["market_name"])
                .field("volume_kg", r["volume_kg"])
                .time(r["date_str"] + "T00:00:00+09:00", WritePrecision.SECONDS)
            )
            points.append(p_vol)

    if points:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        log.info(f"  → InfluxDB에 {len(points)}개 포인트 적재 완료")


# ── 메인 수집 루프 ─────────────────────────────────────────────

def collect_for_date(target_date: str, write_api) -> int:
    """지정 날짜 전체 작목 × 시장 수집. 성공 건수 반환."""
    records = []
    for crop_name, item_code, cls_code in CROPS:
        for market_name, market_code in MARKETS:
            result = fetch_daily_price(item_code, cls_code,
                                       market_code, target_date)
            if result:
                records.append({
                    "crop_name":    crop_name,
                    "market_name":  market_name,
                    "market_code":  market_code,
                    "date_str":     target_date,
                    **result,
                })
                log.info(f"  [{crop_name}/{market_name}] "
                         f"{result['price_per_kg']:,.0f}원/kg  "
                         f"반입량 {result['volume_kg']:,.0f}kg")
            time.sleep(0.3)  # API 과호출 방지

    if records:
        write_to_influx(write_api, records)

    return len(records)


def main():
    parser = argparse.ArgumentParser(description="KAMIS → InfluxDB 수집기")
    parser.add_argument("--date",     type=str, help="수집 날짜 (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="오늘부터 N일 전까지 소급 수집")
    args = parser.parse_args()

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        if args.backfill:
            # 소급 수집: 오늘부터 N일 전까지
            today = date.today()
            dates = [str(today - timedelta(days=i))
                     for i in range(args.backfill, -1, -1)]
            log.info(f"소급 수집 시작: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")
            total = 0
            for d in dates:
                log.info(f"── {d} 수집 중 ──")
                total += collect_for_date(d, write_api)
                time.sleep(1)
            log.info(f"소급 수집 완료: 총 {total}건")

        else:
            # 단일 날짜
            target = args.date or str(date.today())
            log.info(f"── {target} 수집 중 ──")
            count = collect_for_date(target, write_api)
            log.info(f"완료: {count}건")

    finally:
        client.close()


if __name__ == "__main__":
    main()
