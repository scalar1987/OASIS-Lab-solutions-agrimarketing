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
