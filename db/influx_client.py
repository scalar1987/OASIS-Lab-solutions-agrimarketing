"""
db/influx_client.py
InfluxDB Cloud 가격·반입량 시계열 쿼리
"""

import os
import pandas as pd
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

load_dotenv()

_URL    = os.environ["INFLUXDB_URL"]
_TOKEN  = os.environ["INFLUXDB_TOKEN"]
_ORG    = os.environ["INFLUXDB_ORG"]
_BUCKET = os.environ["INFLUXDB_BUCKET"]


def _client() -> InfluxDBClient:
    return InfluxDBClient(url=_URL, token=_TOKEN, org=_ORG)


def _flux_to_df(flux: str, value_col: str) -> pd.DataFrame:
    with _client() as client:
        df = client.query_api().query_data_frame(flux, org=_ORG)
    if df.empty or "_value" not in df.columns:
        return pd.DataFrame(columns=[value_col])
    df = df.rename(columns={"_value": value_col, "_time": "time"})
    df = df[["time", value_col]].set_index("time").sort_index()
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Asia/Seoul")
    return df


def query_price_series(crop_name: str, market_code: str, days: int = 730) -> pd.DataFrame:
    """
    가격 시계열 조회 — Supabase price_history 위임 (InfluxDB 30일 보존 한계 우회)
    """
    from db.supabase_client import query_price_series as _pg_query
    return _pg_query(crop_name, market_code, days)


def query_volume_series(crop_name: str, market_code: str, days: int = 60) -> pd.DataFrame:
    """
    kamis_volume에서 반입량 시계열 조회

    Returns: DataFrame(index=KST datetime, columns=[volume_kg])
    """
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r._measurement == "kamis_volume")
  |> filter(fn: (r) => r.crop_name == "{crop_name}")
  |> filter(fn: (r) => r.market_code == "{market_code}")
  |> filter(fn: (r) => r._field == "volume_kg")
  |> sort(columns: ["_time"])
"""
    return _flux_to_df(flux, "volume_kg")
