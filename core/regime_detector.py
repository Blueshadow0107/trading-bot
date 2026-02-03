"""
ADX Regime Detector
====================
Detects market regime to switch between Mean Reversion and RSI Momentum strategies.

Logic:
- BEAR_TREND: ADX > 25 AND price < SMA_50 → Use RSI Momentum (avoid catching knives)
- DEFAULT: Everything else → Use Mean Reversion (catch early moves, buy dips)

Based on backtest results (Feb 2026):
- Mean Reversion: 4/6 wins (bull runs, sideways)
- RSI Momentum: 2/6 wins (bear trends only)
"""

import numpy as np
from typing import Tuple, Literal

RegimeType = Literal["BEAR_TREND", "DEFAULT"]
StrategyType = Literal["RSI_MOMENTUM", "MEAN_REVERSION"]


def calculate_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """
    Calculate Average Directional Index (ADX).
    
    ADX > 25 indicates a trending market.
    ADX < 20 indicates a ranging market.
    
    Args:
        high: Array of high prices
        low: Array of low prices  
        close: Array of close prices
        period: Lookback period (default 14)
    
    Returns:
        Current ADX value
    """
    if len(close) < period + 1:
        return 0.0
    
    # Calculate True Range
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    
    # Calculate +DM and -DM
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Smooth with Wilder's method (EMA with alpha = 1/period)
    def wilder_smooth(arr, period):
        result = np.zeros_like(arr)
        result[period-1] = np.mean(arr[:period])
        for i in range(period, len(arr)):
            result[i] = result[i-1] - (result[i-1] / period) + arr[i]
        return result
    
    atr = wilder_smooth(tr, period)
    plus_di = 100 * wilder_smooth(plus_dm, period) / np.where(atr > 0, atr, 1)
    minus_di = 100 * wilder_smooth(minus_dm, period) / np.where(atr > 0, atr, 1)
    
    # Calculate DX and ADX
    di_sum = plus_di + minus_di
    dx = 100 * np.abs(plus_di - minus_di) / np.where(di_sum > 0, di_sum, 1)
    adx = wilder_smooth(dx, period)
    
    return float(adx[-1]) if len(adx) > 0 else 0.0


def calculate_sma(prices: np.ndarray, period: int = 50) -> float:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    return float(np.mean(prices[-period:]))


def calculate_ema(prices: np.ndarray, period: int = 200) -> float:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return float(ema)


def detect_regime(
    high: np.ndarray,
    low: np.ndarray, 
    close: np.ndarray,
    adx_threshold: float = 25.0,
    trend_ma_period: int = 50,
    adx_period: int = 14
) -> Tuple[RegimeType, dict]:
    """
    Detect current market regime.
    
    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        adx_threshold: ADX value above which market is considered trending (default 25)
        trend_ma_period: MA period for trend direction (default 50)
        adx_period: ADX calculation period (default 14)
    
    Returns:
        Tuple of (regime, details_dict)
    """
    current_price = float(close[-1])
    adx = calculate_adx(high, low, close, adx_period)
    sma = calculate_sma(close, trend_ma_period)
    ema_200 = calculate_ema(close, 200)
    
    details = {
        "price": current_price,
        "adx": round(adx, 2),
        "sma_50": round(sma, 2),
        "ema_200": round(ema_200, 2),
        "is_trending": adx > adx_threshold,
        "is_below_sma": current_price < sma,
        "is_below_ema200": current_price < ema_200,
    }
    
    # BEAR_TREND: Strong trend + price below moving average
    if adx > adx_threshold and current_price < sma:
        regime = "BEAR_TREND"
    else:
        regime = "DEFAULT"
    
    details["regime"] = regime
    return regime, details


def get_strategy(regime: RegimeType) -> StrategyType:
    """
    Get recommended strategy for the given regime.
    
    Args:
        regime: Current market regime
    
    Returns:
        Recommended strategy name
    """
    if regime == "BEAR_TREND":
        return "RSI_MOMENTUM"
    else:
        return "MEAN_REVERSION"


def analyze_market(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    symbol: str = "BTC/USD"
) -> dict:
    """
    Full market analysis with regime detection and strategy recommendation.
    
    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        symbol: Trading pair symbol
    
    Returns:
        Complete analysis dictionary
    """
    regime, details = detect_regime(high, low, close)
    strategy = get_strategy(regime)
    
    return {
        "symbol": symbol,
        "regime": regime,
        "strategy": strategy,
        "details": details,
        "explanation": _get_explanation(regime, details)
    }


def _get_explanation(regime: RegimeType, details: dict) -> str:
    """Generate human-readable explanation of the regime detection."""
    adx = details["adx"]
    price = details["price"]
    sma = details["sma_50"]
    
    if regime == "BEAR_TREND":
        return (
            f"BEAR TREND detected: ADX={adx} (>{25}=trending) and "
            f"price ${price:.2f} < SMA50 ${sma:.2f}. "
            f"Using RSI Momentum to avoid catching falling knives."
        )
    else:
        trend_status = "trending" if details["is_trending"] else "ranging"
        position = "below" if details["is_below_sma"] else "above"
        return (
            f"DEFAULT regime: Market is {trend_status} (ADX={adx}), "
            f"price ${price:.2f} is {position} SMA50 ${sma:.2f}. "
            f"Using Mean Reversion to catch early moves."
        )


# CLI test
if __name__ == "__main__":
    import sys
    
    # Test with dummy data
    np.random.seed(42)
    n = 100
    close = 50000 + np.cumsum(np.random.randn(n) * 500)
    high = close + np.abs(np.random.randn(n) * 200)
    low = close - np.abs(np.random.randn(n) * 200)
    
    result = analyze_market(high, low, close, "BTC/USD")
    
    print("=" * 60)
    print("ADX REGIME DETECTOR TEST")
    print("=" * 60)
    print(f"Symbol: {result['symbol']}")
    print(f"Regime: {result['regime']}")
    print(f"Strategy: {result['strategy']}")
    print(f"\nDetails:")
    for k, v in result['details'].items():
        print(f"  {k}: {v}")
    print(f"\nExplanation: {result['explanation']}")
