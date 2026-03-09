"""
analyzer/momentum.py
반입량 모멘텀 계산 — 7일 이동평균 기반 변화율
"""

import pandas as pd


def calc_momentum(volume_series: pd.Series, window: int = 7) -> float:
    """
    최근 3일 평균 반입량 vs 직전 7일 평균 반입량 변화율 (%)

    Args:
        volume_series: 반입량 시계열 (DatetimeIndex)
        window:        기준 이동평균 윈도우 (기본 7일)

    Returns:
        모멘텀 %: 양수 = 급증, 음수 = 감소
    """
    if len(volume_series) < window + 3:
        return 0.0

    ma = volume_series.rolling(window=window, min_periods=1).mean()
    recent = ma.iloc[-3:].mean()
    prev   = ma.iloc[-(window + 3):-(window)].mean()

    if pd.isna(prev) or prev == 0:
        return 0.0

    return round(float((recent - prev) / prev * 100), 1)


def interpret_momentum(momentum: float) -> dict:
    """
    모멘텀 수치 → 한글 레이블 + 신호 문자열

    Returns:
        {"label": "급증 (+20%)", "signal": "surge"}
    """
    if momentum >= 15.0:
        return {"label": f"급증 (+{momentum:.0f}%)", "signal": "surge"}
    elif momentum >= 5.0:
        return {"label": f"증가 (+{momentum:.0f}%)", "signal": "increase"}
    elif momentum <= -8.0:
        return {"label": f"감소 ({momentum:.0f}%)", "signal": "drop"}
    elif momentum <= -3.0:
        return {"label": f"소폭 감소 ({momentum:.0f}%)", "signal": "slight_drop"}
    else:
        return {"label": f"보합 ({momentum:+.0f}%)", "signal": "stable"}
