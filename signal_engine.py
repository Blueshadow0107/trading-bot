"""
Signal Engine - Unified signal generation from multiple strategies.

Combines multiple technical analysis strategies into one coherent signal system.
Each strategy votes, and we combine their signals with configurable weights.
"""

import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class SignalType(Enum):
    STRONG_LONG = 2
    LONG = 1
    NEUTRAL = 0
    SHORT = -1
    STRONG_SHORT = -2


@dataclass
class StrategySignal:
    """Output from a single strategy."""
    name: str
    signal: SignalType
    confidence: float  # 0-100
    indicators: Dict[str, float]
    reason: str


@dataclass  
class CompositeSignal:
    """Combined signal from all strategies."""
    symbol: str
    price: float
    signal: SignalType
    confidence: float
    strategies: List[StrategySignal]
    timestamp: datetime
    
    def to_alert_dict(self) -> Dict[str, Any]:
        """Convert to dict format for Discord alerts."""
        side_map = {
            SignalType.STRONG_LONG: 'STRONG BUY',
            SignalType.LONG: 'BUY',
            SignalType.NEUTRAL: 'HOLD',
            SignalType.SHORT: 'SELL',
            SignalType.STRONG_SHORT: 'STRONG SELL'
        }
        return {
            'symbol': self.symbol,
            'side': side_map[self.signal],
            'price': self.price,
            'confidence': round(self.confidence),
            'strategy': ', '.join([s.name for s in self.strategies if s.signal != SignalType.NEUTRAL]),
            'rsi': next((s.indicators.get('rsi') for s in self.strategies if 'rsi' in s.indicators), None)
        }


class SignalEngine:
    """
    Multi-strategy signal generator.
    
    Strategies can be added dynamically. Each strategy analyzes the same
    candle data and produces a signal with confidence. The engine combines
    these into a final recommendation.
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: Optional dict mapping strategy names to weights (default all 1.0)
        """
        self.weights = weights or {}
        self.default_weight = 1.0
    
    def calculate_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(closes) < period + 1:
            return 50.0
            
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_bollinger_bands(self, closes: np.ndarray, period: int = 20, std: int = 2) -> tuple:
        """Calculate Bollinger Bands."""
        if len(closes) < period:
            return closes[-1], closes[-1], closes[-1]
            
        sma = np.mean(closes[-period:])
        std_dev = np.std(closes[-period:])
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, sma, lower
    
    def calculate_ema(self, closes: np.ndarray, period: int) -> float:
        """Calculate EMA."""
        if len(closes) < period:
            return closes[-1]
        
        multiplier = 2 / (period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    def calculate_macd(self, closes: np.ndarray) -> tuple:
        """Calculate MACD."""
        ema12 = self.calculate_ema(closes, 12)
        ema26 = self.calculate_ema(closes, 26)
        macd_line = ema12 - ema26
        
        # Signal line would need more history, simplified here
        signal_line = macd_line * 0.9  # Approximation
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    # === STRATEGIES ===
    
    def strategy_rsi_mean_reversion(self, candles: np.ndarray) -> StrategySignal:
        """RSI + Bollinger Bands mean reversion."""
        closes = candles[:, 4]
        price = closes[-1]
        
        rsi = self.calculate_rsi(closes)
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(closes)
        
        signal = SignalType.NEUTRAL
        confidence = 50.0
        reason = "No clear signal"
        
        if rsi < 30 and price < bb_lower:
            signal = SignalType.STRONG_LONG
            confidence = 80 + (30 - rsi)  # Higher confidence with lower RSI
            reason = f"Oversold: RSI={rsi:.1f}, price below lower BB"
        elif rsi < 35 and price < bb_mid:
            signal = SignalType.LONG
            confidence = 60 + (35 - rsi)
            reason = f"Near oversold: RSI={rsi:.1f}"
        elif rsi > 70 and price > bb_upper:
            signal = SignalType.STRONG_SHORT
            confidence = 80 + (rsi - 70)
            reason = f"Overbought: RSI={rsi:.1f}, price above upper BB"
        elif rsi > 65 and price > bb_mid:
            signal = SignalType.SHORT
            confidence = 60 + (rsi - 65)
            reason = f"Near overbought: RSI={rsi:.1f}"
        
        confidence = min(confidence, 100)
        
        return StrategySignal(
            name="RSI Mean Reversion",
            signal=signal,
            confidence=confidence,
            indicators={'rsi': round(rsi, 2), 'bb_lower': bb_lower, 'bb_upper': bb_upper},
            reason=reason
        )
    
    def strategy_golden_cross(self, candles: np.ndarray) -> StrategySignal:
        """EMA crossover trend following."""
        closes = candles[:, 4]
        
        fast_ema = self.calculate_ema(closes, 8)
        slow_ema = self.calculate_ema(closes, 21)
        
        prev_fast = self.calculate_ema(closes[:-1], 8) if len(closes) > 1 else fast_ema
        prev_slow = self.calculate_ema(closes[:-1], 21) if len(closes) > 1 else slow_ema
        
        signal = SignalType.NEUTRAL
        confidence = 50.0
        reason = "No crossover"
        
        # Golden cross
        if prev_fast <= prev_slow and fast_ema > slow_ema:
            signal = SignalType.LONG
            confidence = 70.0
            reason = "Golden cross: Fast EMA crossed above Slow EMA"
        # Death cross
        elif prev_fast >= prev_slow and fast_ema < slow_ema:
            signal = SignalType.SHORT
            confidence = 70.0
            reason = "Death cross: Fast EMA crossed below Slow EMA"
        # In uptrend
        elif fast_ema > slow_ema:
            signal = SignalType.LONG
            confidence = 55.0
            reason = "Uptrend: Fast EMA above Slow EMA"
        # In downtrend
        elif fast_ema < slow_ema:
            signal = SignalType.SHORT
            confidence = 55.0
            reason = "Downtrend: Fast EMA below Slow EMA"
        
        return StrategySignal(
            name="Golden Cross",
            signal=signal,
            confidence=confidence,
            indicators={'fast_ema': round(fast_ema, 2), 'slow_ema': round(slow_ema, 2)},
            reason=reason
        )
    
    def strategy_macd(self, candles: np.ndarray) -> StrategySignal:
        """MACD momentum strategy."""
        closes = candles[:, 4]
        
        macd_line, signal_line, histogram = self.calculate_macd(closes)
        
        signal = SignalType.NEUTRAL
        confidence = 50.0
        reason = "No clear MACD signal"
        
        if histogram > 0 and macd_line > 0:
            signal = SignalType.LONG
            confidence = 60 + min(abs(histogram) * 10, 30)
            reason = f"Bullish MACD: histogram={histogram:.4f}"
        elif histogram < 0 and macd_line < 0:
            signal = SignalType.SHORT
            confidence = 60 + min(abs(histogram) * 10, 30)
            reason = f"Bearish MACD: histogram={histogram:.4f}"
        
        confidence = min(confidence, 100)
        
        return StrategySignal(
            name="MACD",
            signal=signal,
            confidence=confidence,
            indicators={'macd': round(macd_line, 4), 'signal': round(signal_line, 4), 'histogram': round(histogram, 4)},
            reason=reason
        )
    
    def analyze(self, symbol: str, candles: np.ndarray) -> CompositeSignal:
        """
        Run all strategies and produce composite signal.
        
        Args:
            symbol: Trading pair symbol
            candles: OHLCV data as numpy array [time, open, high, low, close, volume]
        
        Returns:
            CompositeSignal with combined analysis
        """
        price = candles[-1, 4]
        
        # Run all strategies
        strategies = [
            self.strategy_rsi_mean_reversion(candles),
            self.strategy_golden_cross(candles),
            self.strategy_macd(candles),
        ]
        
        # Weight and combine signals
        total_weight = 0
        weighted_signal = 0
        weighted_confidence = 0
        
        for strat in strategies:
            weight = self.weights.get(strat.name, self.default_weight)
            weighted_signal += strat.signal.value * weight * (strat.confidence / 100)
            weighted_confidence += strat.confidence * weight
            total_weight += weight
        
        if total_weight > 0:
            avg_signal = weighted_signal / total_weight
            avg_confidence = weighted_confidence / total_weight
        else:
            avg_signal = 0
            avg_confidence = 50
        
        # Map back to SignalType
        if avg_signal >= 1.5:
            final_signal = SignalType.STRONG_LONG
        elif avg_signal >= 0.5:
            final_signal = SignalType.LONG
        elif avg_signal <= -1.5:
            final_signal = SignalType.STRONG_SHORT
        elif avg_signal <= -0.5:
            final_signal = SignalType.SHORT
        else:
            final_signal = SignalType.NEUTRAL
        
        return CompositeSignal(
            symbol=symbol,
            price=price,
            signal=final_signal,
            confidence=avg_confidence,
            strategies=strategies,
            timestamp=datetime.now()
        )


if __name__ == '__main__':
    # Test with sample data
    import requests
    
    def fetch_candles(symbol='XXBTZUSD', interval=60, count=100):
        url = "https://api.kraken.com/0/public/OHLC"
        params = {'pair': symbol, 'interval': interval}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('error'):
            return None
        
        result = data['result']
        pair_key = [k for k in result.keys() if k != 'last'][0]
        candles = result[pair_key][-count:]
        
        return np.array([[float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])] for c in candles])
    
    print("🔍 Signal Engine Test")
    print("=" * 50)
    
    engine = SignalEngine()
    
    for symbol in ['XXBTZUSD', 'XETHZUSD']:
        print(f"\n📊 Analyzing {symbol}...")
        candles = fetch_candles(symbol)
        
        if candles is not None:
            result = engine.analyze(symbol, candles)
            
            print(f"   Price: ${result.price:,.2f}")
            print(f"   Signal: {result.signal.name}")
            print(f"   Confidence: {result.confidence:.1f}%")
            print(f"   Strategies:")
            for s in result.strategies:
                print(f"     - {s.name}: {s.signal.name} ({s.confidence:.0f}%) - {s.reason}")
