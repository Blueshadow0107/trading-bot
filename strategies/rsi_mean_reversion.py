"""
RSI Mean Reversion Strategy for Jesse.trade

Buy when:
- RSI < 30 (oversold)
- Price below lower Bollinger Band

Sell when:
- RSI > 70 (overbought)  
- Price above upper Bollinger Band

Risk Management:
- Stop loss: 5%
- Take profit: 5%
- Position size: 5% of capital
"""

from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils


class RSIMeanReversion(Strategy):
    
    @property
    def rsi(self):
        return ta.rsi(self.candles, period=14)
    
    @property
    def bb(self):
        return ta.bollinger_bands(self.candles, period=20, devup=2, devdn=2)
    
    @property
    def bb_lower(self):
        return self.bb[2]
    
    @property
    def bb_upper(self):
        return self.bb[0]
    
    def should_long(self) -> bool:
        # Buy when oversold (RSI < 30) AND price below lower Bollinger Band
        return self.rsi < 30 and self.price < self.bb_lower
    
    def should_short(self) -> bool:
        # Short when overbought (RSI > 70) AND price above upper Bollinger Band
        return self.rsi > 70 and self.price > self.bb_upper
    
    def should_cancel_entry(self) -> bool:
        return False
    
    def go_long(self):
        # Position size: 5% of capital
        qty = utils.size_to_qty(self.balance * 0.05, self.price)
        
        self.buy = qty, self.price
        self.stop_loss = qty, self.price * 0.95   # 5% stop loss
        self.take_profit = qty, self.price * 1.05  # 5% take profit
    
    def go_short(self):
        # Position size: 5% of capital
        qty = utils.size_to_qty(self.balance * 0.05, self.price)
        
        self.sell = qty, self.price
        self.stop_loss = qty, self.price * 1.05   # 5% stop loss
        self.take_profit = qty, self.price * 0.95  # 5% take profit
    
    def update_position(self):
        # Optional: trailing stop or dynamic exit logic
        pass
    
    # Hyperparameters for optimization
    def hyperparameters(self):
        return [
            {'name': 'rsi_period', 'type': int, 'min': 10, 'max': 20, 'default': 14},
            {'name': 'rsi_oversold', 'type': int, 'min': 20, 'max': 35, 'default': 30},
            {'name': 'rsi_overbought', 'type': int, 'min': 65, 'max': 80, 'default': 70},
            {'name': 'bb_period', 'type': int, 'min': 15, 'max': 30, 'default': 20},
            {'name': 'stop_loss_pct', 'type': float, 'min': 0.03, 'max': 0.10, 'default': 0.05},
            {'name': 'take_profit_pct', 'type': float, 'min': 0.03, 'max': 0.15, 'default': 0.05},
        ]
