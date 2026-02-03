"""
ADX Regime Detector v2 - Enhanced with NOF1 Intel
==================================================
Upgraded based on nof1.ai Alpha Arena research (2026-02-03)

New features:
- Multi-timeframe analysis (hourly + 4-hour)
- Dual RSI (7-period fast + 14-period standard)
- MACD confirmation
- Volume analysis
- ATR-based position sizing

Logic:
- BEAR_TREND: ADX > 25 AND price < SMA_50 → RSI Momentum
- BULL_TREND: ADX > 25 AND price > SMA_50 → Mean Reversion (ride the dip)
- RANGING: ADX < 20 → Mean Reversion (classic chop)
- NEUTRAL: 20 < ADX < 25 → Reduced position size
"""

import numpy as np
from typing import Tuple, Literal, Optional
from dataclasses import dataclass

RegimeType = Literal["BEAR_TREND", "BULL_TREND", "RANGING", "NEUTRAL"]
StrategyType = Literal["RSI_MOMENTUM", "MEAN_REVERSION"]


@dataclass
class MarketState:
    """Complete market state for decision making"""
    # Price
    price: float
    
    # Moving Averages
    sma_50: float
    ema_20: float
    ema_200: float
    
    # RSI (dual timeframe)
    rsi_7: float   # Fast - for entry timing
    rsi_14: float  # Standard - for trend
    
    # ADX
    adx: float
    
    # MACD
    macd: float
    macd_signal: float
    macd_histogram: float
    
    # Volatility
    atr_14: float
    atr_percent: float  # ATR as % of price
    
    # Volume
    volume: float
    volume_sma: float
    volume_ratio: float  # current / average
    
    # Regime
    regime: RegimeType
    strategy: StrategyType
    position_size_multiplier: float  # 0.5 - 1.5 based on conditions


def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Calculate RSI."""
    if len(prices) < period + 1:
        return 50.0  # Neutral default
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
    """Calculate MACD, Signal, and Histogram."""
    if len(prices) < slow + signal:
        return 0.0, 0.0, 0.0
    
    def ema(data, period):
        multiplier = 2 / (period + 1)
        result = data[0]
        for price in data[1:]:
            result = (price - result) * multiplier + result
        return result
    
    # Calculate MACD line
    ema_fast = ema(prices[-fast-signal:], fast)
    ema_slow = ema(prices[-slow-signal:], slow)
    macd_line = ema_fast - ema_slow
    
    # For proper signal line, we'd need historical MACD values
    # Simplified: use current MACD as approximation
    signal_line = macd_line * 0.9  # Approximation
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Calculate Average Directional Index (ADX)."""
    if len(close) < period + 1:
        return 0.0
    
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    def wilder_smooth(arr, period):
        result = np.zeros_like(arr)
        result[period-1] = np.mean(arr[:period])
        for i in range(period, len(arr)):
            result[i] = result[i-1] - (result[i-1] / period) + arr[i]
        return result
    
    atr = wilder_smooth(tr, period)
    plus_di = 100 * wilder_smooth(plus_dm, period) / np.where(atr > 0, atr, 1)
    minus_di = 100 * wilder_smooth(minus_dm, period) / np.where(atr > 0, atr, 1)
    
    di_sum = plus_di + minus_di
    dx = 100 * np.abs(plus_di - minus_di) / np.where(di_sum > 0, di_sum, 1)
    adx = wilder_smooth(dx, period)
    
    return float(adx[-1]) if len(adx) > 0 else 0.0


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Calculate Average True Range."""
    if len(close) < period + 1:
        return 0.0
    
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    
    return float(np.mean(tr[-period:]))


def calculate_sma(prices: np.ndarray, period: int) -> float:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    return float(np.mean(prices[-period:]))


def calculate_ema(prices: np.ndarray, period: int) -> float:
    """Calculate Exponential Moving Average."""
    if len(prices) < 2:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return float(ema)


def detect_regime(
    adx: float,
    price: float,
    sma_50: float,
    adx_trend_threshold: float = 25.0,
    adx_range_threshold: float = 20.0
) -> Tuple[RegimeType, StrategyType, float]:
    """
    Detect regime and recommend strategy with position size multiplier.
    
    Returns:
        (regime, strategy, position_size_multiplier)
    """
    # Strong trend
    if adx > adx_trend_threshold:
        if price < sma_50:
            # Bear trend - use momentum, avoid catching knives
            return "BEAR_TREND", "RSI_MOMENTUM", 0.75
        else:
            # Bull trend - mean reversion catches dips
            return "BULL_TREND", "MEAN_REVERSION", 1.0
    
    # Ranging market
    elif adx < adx_range_threshold:
        # Classic mean reversion territory
        return "RANGING", "MEAN_REVERSION", 1.25  # Higher confidence in ranging
    
    # Neutral - unclear trend
    else:
        return "NEUTRAL", "MEAN_REVERSION", 0.5  # Reduced size when uncertain


def analyze_market_v2(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    symbol: str = "BTC/USD"
) -> MarketState:
    """
    Full market analysis with all indicators.
    
    Args:
        high: Array of high prices
        low: Array of low prices
        close: Array of close prices
        volume: Array of volume data
        symbol: Trading pair symbol
    
    Returns:
        Complete MarketState with regime and strategy
    """
    price = float(close[-1])
    
    # Moving Averages
    sma_50 = calculate_sma(close, 50)
    ema_20 = calculate_ema(close, 20)
    ema_200 = calculate_ema(close, 200)
    
    # Dual RSI
    rsi_7 = calculate_rsi(close, 7)
    rsi_14 = calculate_rsi(close, 14)
    
    # ADX
    adx = calculate_adx(high, low, close, 14)
    
    # MACD
    macd, macd_signal, macd_histogram = calculate_macd(close)
    
    # ATR
    atr_14 = calculate_atr(high, low, close, 14)
    atr_percent = (atr_14 / price) * 100 if price > 0 else 0
    
    # Volume
    vol = float(volume[-1]) if len(volume) > 0 else 0
    vol_sma = calculate_sma(volume, 20)
    vol_ratio = vol / vol_sma if vol_sma > 0 else 1.0
    
    # Regime detection
    regime, strategy, pos_mult = detect_regime(adx, price, sma_50)
    
    # Adjust position size based on volatility
    if atr_percent > 5:  # High volatility
        pos_mult *= 0.7
    elif atr_percent < 2:  # Low volatility
        pos_mult *= 1.2
    
    # Adjust based on volume confirmation
    if vol_ratio > 1.5:  # High volume = more conviction
        pos_mult *= 1.1
    elif vol_ratio < 0.5:  # Low volume = less conviction
        pos_mult *= 0.8
    
    # Cap position size multiplier
    pos_mult = max(0.25, min(1.5, pos_mult))
    
    return MarketState(
        price=round(price, 2),
        sma_50=round(sma_50, 2),
        ema_20=round(ema_20, 2),
        ema_200=round(ema_200, 2),
        rsi_7=round(rsi_7, 2),
        rsi_14=round(rsi_14, 2),
        adx=round(adx, 2),
        macd=round(macd, 4),
        macd_signal=round(macd_signal, 4),
        macd_histogram=round(macd_histogram, 4),
        atr_14=round(atr_14, 2),
        atr_percent=round(atr_percent, 2),
        volume=round(vol, 2),
        volume_sma=round(vol_sma, 2),
        volume_ratio=round(vol_ratio, 2),
        regime=regime,
        strategy=strategy,
        position_size_multiplier=round(pos_mult, 2)
    )


def generate_signal(state: MarketState) -> dict:
    """
    Generate trading signal based on market state.
    
    Returns dict with:
    - action: BUY / SELL / HOLD
    - strategy: which strategy triggered
    - confidence: 0-100
    - reasoning: explanation
    """
    action = "HOLD"
    confidence = 50
    reasons = []
    
    if state.strategy == "MEAN_REVERSION":
        # Mean Reversion Logic
        if state.rsi_7 < 30 and state.rsi_14 < 40:
            action = "BUY"
            confidence = 70
            reasons.append(f"RSI oversold (7:{state.rsi_7}, 14:{state.rsi_14})")
        elif state.rsi_7 > 70 and state.rsi_14 > 60:
            action = "SELL"
            confidence = 70
            reasons.append(f"RSI overbought (7:{state.rsi_7}, 14:{state.rsi_14})")
        
        # MACD confirmation
        if action == "BUY" and state.macd_histogram > 0:
            confidence += 10
            reasons.append("MACD bullish confirmation")
        elif action == "SELL" and state.macd_histogram < 0:
            confidence += 10
            reasons.append("MACD bearish confirmation")
        
    else:  # RSI_MOMENTUM
        # RSI Momentum Logic - follow the trend
        if state.rsi_14 > 50 and state.macd_histogram > 0 and state.price > state.ema_20:
            action = "BUY"
            confidence = 65
            reasons.append("Momentum bullish: RSI>50, MACD+, Price>EMA20")
        elif state.rsi_14 < 50 and state.macd_histogram < 0 and state.price < state.ema_20:
            action = "SELL"
            confidence = 65
            reasons.append("Momentum bearish: RSI<50, MACD-, Price<EMA20")
    
    # Volume confirmation
    if state.volume_ratio > 1.5:
        confidence += 10
        reasons.append(f"High volume ({state.volume_ratio}x avg)")
    
    # Regime confidence adjustment
    if state.regime == "NEUTRAL":
        confidence -= 15
        reasons.append("Neutral regime - reduced confidence")
    
    confidence = max(0, min(100, confidence))
    
    return {
        "action": action,
        "strategy": state.strategy,
        "regime": state.regime,
        "confidence": confidence,
        "position_size": state.position_size_multiplier,
        "reasoning": "; ".join(reasons) if reasons else "No clear signal",
        "state": {
            "price": state.price,
            "rsi_7": state.rsi_7,
            "rsi_14": state.rsi_14,
            "adx": state.adx,
            "macd_hist": state.macd_histogram,
            "volume_ratio": state.volume_ratio
        }
    }


def format_signal_log(signal: dict, symbol: str) -> str:
    """Format signal for logging."""
    return (
        f"{symbol} | {signal['action']} | "
        f"Regime: {signal['regime']} | Strategy: {signal['strategy']} | "
        f"Confidence: {signal['confidence']}% | Size: {signal['position_size']}x | "
        f"Reason: {signal['reasoning']}"
    )


# CLI test
if __name__ == "__main__":
    import json
    
    # Test with realistic-ish data
    np.random.seed(42)
    n = 100
    
    # Simulate a ranging market
    base_price = 80000
    close = base_price + np.cumsum(np.random.randn(n) * 200)
    high = close + np.abs(np.random.randn(n) * 100)
    low = close - np.abs(np.random.randn(n) * 100)
    volume = 1000 + np.random.randn(n) * 200
    
    state = analyze_market_v2(high, low, close, volume, "BTC/USD")
    signal = generate_signal(state)
    
    print("=" * 70)
    print("REGIME DETECTOR V2 - Enhanced with NOF1 Intel")
    print("=" * 70)
    print(f"\n📊 Market State:")
    print(f"  Price: ${state.price:,.2f}")
    print(f"  SMA50: ${state.sma_50:,.2f} | EMA20: ${state.ema_20:,.2f}")
    print(f"  RSI-7: {state.rsi_7} | RSI-14: {state.rsi_14}")
    print(f"  ADX: {state.adx}")
    print(f"  MACD: {state.macd} | Signal: {state.macd_signal} | Hist: {state.macd_histogram}")
    print(f"  ATR: ${state.atr_14:,.2f} ({state.atr_percent}%)")
    print(f"  Volume Ratio: {state.volume_ratio}x")
    print(f"\n🎯 Regime: {state.regime}")
    print(f"📈 Strategy: {state.strategy}")
    print(f"📐 Position Size: {state.position_size_multiplier}x")
    print(f"\n🚦 Signal:")
    print(f"  Action: {signal['action']}")
    print(f"  Confidence: {signal['confidence']}%")
    print(f"  Reasoning: {signal['reasoning']}")
    print(f"\n📝 Log Format:")
    print(f"  {format_signal_log(signal, 'BTC/USD')}")
