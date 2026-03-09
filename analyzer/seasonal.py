"""
analyzer/seasonal.py
계절성 가격 분위 계산 — 평년 동월 대비 현재 가격 백분위
"""

import numpy as np
import pandas as pd


def calc_price_percentile(
    current_price: float,
    price_series: pd.Series,
    month: int,
) -> float:
    """
    현재 가격이 평년 동월 대비 몇 분위인지 계산 (0~100)

    Args:
        current_price: 현재 가격 (원/kg)
        price_series:  과거 가격 시계열 (DatetimeIndex 필요)
        month:         현재 월 (1~12)

    Returns:
        백분위 0.0 ~ 100.0  (70 = 상위 30% 구간 = 고점)
    """
    # 동월 데이터 필터링 (최소 10개 이상이면 동월 기준 사용)
    same_month = price_series[price_series.index.month == month]
    reference = same_month if len(same_month) >= 10 else price_series

    if reference.empty:
        return 50.0

    pct = float(np.sum(reference <= current_price) / len(reference) * 100)
    return round(pct, 1)
