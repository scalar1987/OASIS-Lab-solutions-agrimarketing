"""
engine/prescriber.py
유통 처방 의사결정 엔진

입력:  InfluxDB에서 읽은 가격·반입량 시계열
출력:  처방 결과 dict → Supabase 저장
"""

from datetime import date
from db.influx_client import query_price_series, query_volume_series
from db.supabase_client import save_prescription
from analyzer.seasonal import calc_price_percentile
from analyzer.momentum import calc_momentum, interpret_momentum

# 작목별 설정
CROP_CONFIG = {
    "배추": {"code": "211", "storable": False},
    "고추": {"code": "243", "storable": True},
    "양파": {"code": "245", "storable": True},
    "마늘": {"code": "244", "storable": True},
    "대파": {"code": "246", "storable": False},
    "감자": {"code": "152", "storable": True},
    "사과": {"code": "411", "storable": True},
    "배":   {"code": "412", "storable": True},
    "포도": {"code": "414", "storable": False},
}

# 처방 임계값
PERCENTILE_HIGH = 70.0   # 이상 → 고점 구간
PERCENTILE_LOW  = 30.0   # 이하 → 저점 구간
MOMENTUM_SURGE  = 15.0   # 이상 → 반입량 급증
MOMENTUM_DROP   = -8.0   # 이하 → 반입량 감소


def generate_prescription(crop_name: str,
                           market_code: str = "0110211",
                           target_date: date | None = None) -> dict:
    """
    단일 작목 처방 생성

    처방 의사결정 트리:
      1. 가격 분위 확인 (평년 동월 대비)
         ├─ 상위 30% (≥70%ile) → SHIP_NOW (즉시 출하)
         ├─ 하위 30% (≤30%ile)
         │    ├─ 저장 가능   → WAIT (가격 회복 대기)
         │    └─ 저장 불가   → SHIP_NOW_URGENT (즉시 출하, 품질 손실 위험)
         └─ 중간 구간 → 반입량 모멘텀 확인
              ├─ 급증(>+15%) → SHIP_WITHIN_WEEK
              ├─ 감소(<-8%)  → WAIT_7_10
              └─ 보합        → MONITOR
    """
    if target_date is None:
        target_date = date.today()

    cfg = CROP_CONFIG.get(crop_name)
    if not cfg:
        raise ValueError(f"알 수 없는 작목: {crop_name}")

    # ── 데이터 읽기 ───────────────────────────────────────────
    price_df  = query_price_series(crop_name, market_code, days=730)  # 2년치
    volume_df = query_volume_series(crop_name, market_code, days=60)

    if price_df.empty:
        raise RuntimeError(f"가격 데이터 없음: {crop_name}")

    current_price = float(price_df["price_per_kg"].iloc[-1])
    current_month = target_date.month
    storable      = cfg["storable"]

    # ── 분석 ──────────────────────────────────────────────────
    percentile = calc_price_percentile(
        current_price, price_df["price_per_kg"], current_month
    )
    momentum = (
        calc_momentum(volume_df["volume_kg"])
        if not volume_df.empty else 0.0
    )
    mom_info = interpret_momentum(momentum)

    # ── 처방 의사결정 트리 ────────────────────────────────────
    if percentile >= PERCENTILE_HIGH:
        rx_type = "SHIP_NOW"
        rx_message = f"✅ 즉시 출하 권장 — 현재 {crop_name} 가격 고점 구간"
        rx_reason  = (
            f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 "
            f"평년 동월({current_month}월) 대비 상위 {100-percentile:.0f}% 구간입니다. "
            f"반입량 {mom_info['label']}. "
            f"{'가격 하락 전 선제 출하를 권장합니다.' if momentum > 10 else '고점에서 즉시 출하가 유리합니다.'}"
        )

    elif percentile <= PERCENTILE_LOW:
        if storable:
            rx_type = "WAIT"
            rx_message = f"⏳ 출하 대기 — 가격 저점, 회복 후 출하 유리"
            rx_reason  = (
                f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 "
                f"평년 동월 대비 하위 {percentile:.0f}% 저점 구간입니다. "
                f"{crop_name}은 저장이 가능하므로 가격 회복을 기다리는 전략이 유리합니다. "
                f"반입량 {mom_info['label']}."
            )
        else:
            rx_type = "SHIP_NOW_URGENT"
            rx_message = f"⚠️ 즉시 출하 필요 — 저장 불가, 품질 손실 위험"
            rx_reason  = (
                f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 저점 구간이나, "
                f"{crop_name}은 장기 저장이 어렵습니다. "
                f"품질 손실로 인한 손실이 가격 회복 이익을 초과할 가능성이 높습니다. "
                f"즉시 출하하여 손실을 최소화하세요."
            )

    elif momentum >= MOMENTUM_SURGE:
        rx_type = "SHIP_WITHIN_WEEK"
        rx_message = f"📊 이번 주 내 출하 권장 — 반입량 급증 신호"
        rx_reason  = (
            f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 중간 구간이나, "
            f"반입량이 7일 이동평균 대비 +{momentum:.0f}% 급증했습니다. "
            f"공급 과잉으로 3~5일 내 가격 하락 가능성이 있습니다. "
            f"이번 주 내 출하를 권장합니다."
        )

    elif momentum <= MOMENTUM_DROP:
        rx_type = "WAIT_7_10"
        rx_message = f"📈 7~10일 후 출하 권장 — 반입량 감소, 가격 개선 예상"
        rx_reason  = (
            f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 중간 구간이며, "
            f"반입량이 7일 이동평균 대비 {momentum:.0f}% 감소하고 있습니다. "
            f"공급 감소로 7~10일 내 가격 개선이 예상됩니다."
        )

    else:
        rx_type = "MONITOR"
        rx_message = f"📋 수급 보합 — 3일 후 재판단"
        rx_reason  = (
            f"현재 {crop_name} 도매가 {current_price:,.0f}원/kg은 중간 구간이며 "
            f"반입량 변화도 보합세({momentum:+.0f}%)입니다. "
            f"3일 후 재판단을 권장합니다."
        )

    # SMS 텍스트 생성
    rx_sms = (
        f"[OASIS Lab 유통처방]\n"
        f"{rx_message}\n"
        f"현재가: {current_price:,.0f}원/kg\n"
        f"근거: {rx_reason[:80]}...\n"
        f"oasis-lab.kr"
    )

    result = {
        "crop_name":        crop_name,
        "crop_code":        cfg["code"],
        "rx_type":          rx_type,
        "rx_message":       rx_message,
        "rx_reason":        rx_reason,
        "rx_sms":           rx_sms,
        "current_price":    int(current_price),
        "price_percentile": round(percentile, 1),
        "volume_momentum":  round(momentum, 1),
        "storable":         storable,
        "market_code":      market_code,
        "data_date":        str(target_date),
    }

    return result


def run_all_prescriptions(save: bool = True) -> list[dict]:
    """
    전체 작목 처방 생성 + Supabase 저장
    APScheduler에서 매일 07:00 호출
    """
    results = []
    for crop_name in CROP_CONFIG:
        try:
            rx = generate_prescription(crop_name)
            print(f"[{crop_name}] {rx['rx_type']} — {rx['current_price']:,}원/kg "
                  f"({rx['price_percentile']:.0f}%ile, 모멘텀 {rx['volume_momentum']:+.0f}%)")
            if save:
                save_prescription(rx)
            results.append(rx)
        except Exception as e:
            print(f"[{crop_name}] 처방 실패: {e}")

    return results
