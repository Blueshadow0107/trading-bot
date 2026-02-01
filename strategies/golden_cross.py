"""
Golden Cross Strategy for Jesse.trade

Simple trend-following strategy using EMA crossovers.

Buy when:
- Fast EMA (8) crosses above Slow EMA (21)

Sell when:
- Fast EMA (8) crosses below Slow EMA (21)

Best for:
- Trending markets
- Longer timeframes (4H, 1D)
- Less volatile pairs
"""

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class GoldenCross(Strategy):
    
    @property
    def fast_ema(self):
        return ta.ema(self.candles, period=8)
    
    @property
    def slow_ema(self):
        return ta.ema(self.candles, period=21)
    
    @property
    def prev_fast_ema(self):
        return ta.ema(self.candles[:-1], period=8)
    
    @property
    def prev_slow_ema(self):
        return ta.ema(self.candles[:-1], period=21)
    
    def should_long(self) -> bool:
        # Golden cross: fast EMA crosses above slow EMA
        cross_above = self.prev_fast_ema <= self.prev_slow_ema and self.fast_ema > self.slow_ema
        return cross_above
    
    def should_short(self) -> bool:
        # Death cross: fast EMA crosses below slow EMA
        cross_below = self.prev_fast_ema >= self.prev_slow_ema and self.fast_ema < self.slow_ema
        return cross_below
    
    def should_cancel_entry(self) -> bool:
        return False
    
    def go_long(self):
        # Position size: 5% of capital
        qty = utils.size_to_qty(self.balance * 0.05, self.price)
        
        self.buy = qty, self.price
        self.stop_loss = qty, self.price * 0.90   # 10% stop loss (wider for trend following)
        self.take_profit = qty, self.price * 1.20  # 20% take profit
    
    def go_short(self):
        qty = utils.size_to_qty(self.balance * 0.05, self.price)
        
        self.sell = qty, self.price
        self.stop_loss = qty, self.price * 1.10
        self.take_profit = qty, self.price * 0.80
    
    def update_position(self):
        # Exit on opposite signal (trend reversal)
        if self.is_long and self.fast_ema < self.slow_ema:
            self.liquidate()
        elif self.is_short and self.fast_ema > self.slow_ema:
            self.liquidate()
    
    def hyperparameters(self):
        return [
            {'name': 'fast_period', 'type': int, 'min': 5, 'max': 15, 'default': 8},
            {'name': 'slow_period', 'type': int, 'min': 15, 'max': 50, 'default': 21},
            {'name': 'stop_loss_pct', 'type': float, 'min': 0.05, 'max': 0.15, 'default': 0.10},
            {'name': 'take_profit_pct', 'type': float, 'min': 0.10, 'max': 0.30, 'default': 0.20},
        ]
