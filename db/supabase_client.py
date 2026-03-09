"""
db/supabase_client.py
Supabase 처방 결과 저장 (service_role key → RLS 우회)
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_URL = os.environ["SUPABASE_URL"]
_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def _client() -> Client:
    return create_client(_URL, _KEY)


def save_prescription(rx: dict) -> dict:
    """
    처방 결과를 prescriptions 테이블에 INSERT.
    같은 날짜·작목 처방이 이미 있으면 무시(중복 허용).
    """
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
