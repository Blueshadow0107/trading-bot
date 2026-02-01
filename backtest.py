#!/usr/bin/env python3
"""
Simple Backtester for Trading Strategies

Tests the signal engine against historical data from Kraken.

Usage:
    python3 backtest.py                          # Default: BTC, last 720 candles
    python3 backtest.py --pair ETH --candles 500 # Custom
    python3 backtest.py --all                    # All supported pairs
"""

import argparse
from datetime import datetime
from typing import List, Dict, Any
import requests
import numpy as np

from signal_engine import SignalEngine, SignalType


# Pair mapping
PAIRS = {
    'BTC': 'XXBTZUSD',
    'ETH': 'XETHZUSD', 
    'SOL': 'SOLUSD',
    'XRP': 'XXRPZUSD',
    'ADA': 'ADAUSD',
}


def fetch_candles(pair: str, interval: int = 60, count: int = 720) -> np.ndarray:
    """Fetch historical candles from Kraken."""
    kraken_pair = PAIRS.get(pair, pair)
    url = "https://api.kraken.com/0/public/OHLC"
    params = {'pair': kraken_pair, 'interval': interval}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data.get('error'):
            print(f"❌ Error fetching {pair}: {data['error']}")
            return None
        
        result = data['result']
        pair_key = [k for k in result.keys() if k != 'last'][0]
        candles = result[pair_key][-count:]
        
        return np.array([
            [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])]
            for c in candles
        ])
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


class Backtester:
    """Simple backtester for signal engine."""
    
    def __init__(
        self,
        starting_balance: float = 10000,
        position_size_pct: float = 0.10,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.05,
        min_confidence: float = 65
    ):
        self.starting_balance = starting_balance
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_confidence = min_confidence
        
        self.engine = SignalEngine()
    
    def run(self, pair: str, candles: np.ndarray, lookback: int = 50) -> Dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            pair: Trading pair symbol
            candles: OHLCV numpy array
            lookback: Number of candles needed for indicators
        
        Returns:
            Backtest results dictionary
        """
        balance = self.starting_balance
        position = None  # {side, entry_price, qty, entry_idx}
        trades = []
        signals = []
        
        print(f"\n🔄 Running backtest on {pair}...")
        print(f"   Candles: {len(candles)} | Lookback: {lookback}")
        print(f"   Period: {datetime.fromtimestamp(candles[0, 0])} to {datetime.fromtimestamp(candles[-1, 0])}")
        
        # Iterate through candles
        for i in range(lookback, len(candles)):
            # Get window of candles for analysis
            window = candles[i-lookback:i+1]
            current_price = candles[i, 4]
            
            # Check exit conditions if in position
            if position:
                pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                if position['side'] == 'short':
                    pnl_pct = -pnl_pct
                
                exit_reason = None
                
                if pnl_pct <= -self.stop_loss_pct:
                    exit_reason = 'stop_loss'
                elif pnl_pct >= self.take_profit_pct:
                    exit_reason = 'take_profit'
                
                if exit_reason:
                    pnl = (current_price - position['entry_price']) * position['qty']
                    if position['side'] == 'short':
                        pnl = -pnl
                    
                    balance += pnl
                    
                    trades.append({
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct * 100,
                        'reason': exit_reason,
                        'entry_idx': position['entry_idx'],
                        'exit_idx': i
                    })
                    
                    position = None
            
            # Generate signal
            signal = self.engine.analyze(pair, window)
            signals.append({
                'idx': i,
                'signal': signal.signal,
                'confidence': signal.confidence,
                'price': current_price
            })
            
            # Only trade if no position and signal is actionable
            if not position and signal.signal != SignalType.NEUTRAL:
                if signal.confidence >= self.min_confidence:
                    side = 'long' if signal.signal in [SignalType.LONG, SignalType.STRONG_LONG] else 'short'
                    position_value = balance * self.position_size_pct
                    qty = position_value / current_price
                    
                    position = {
                        'side': side,
                        'entry_price': current_price,
                        'qty': qty,
                        'entry_idx': i,
                        'signal_confidence': signal.confidence
                    }
        
        # Close any remaining position at end
        if position:
            current_price = candles[-1, 4]
            pnl = (current_price - position['entry_price']) * position['qty']
            if position['side'] == 'short':
                pnl = -pnl
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
            
            balance += pnl
            trades.append({
                'side': position['side'],
                'entry_price': position['entry_price'],
                'exit_price': current_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct * 100,
                'reason': 'end_of_test',
                'entry_idx': position['entry_idx'],
                'exit_idx': len(candles) - 1
            })
        
        # Calculate stats
        total_pnl = balance - self.starting_balance
        total_pnl_pct = (total_pnl / self.starting_balance) * 100
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        results = {
            'pair': pair,
            'starting_balance': self.starting_balance,
            'final_balance': balance,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'trades': trades,
            'total_signals': len(signals),
            'actionable_signals': len([s for s in signals if s['signal'] != SignalType.NEUTRAL])
        }
        
        return results
    
    def print_results(self, results: Dict[str, Any]):
        """Print backtest results nicely."""
        print(f"\n{'='*60}")
        print(f"📊 BACKTEST RESULTS: {results['pair']}")
        print(f"{'='*60}")
        print(f"Starting Balance:  ${results['starting_balance']:,.2f}")
        print(f"Final Balance:     ${results['final_balance']:,.2f}")
        print(f"Total PnL:         ${results['total_pnl']:,.2f} ({results['total_pnl_pct']:+.2f}%)")
        print()
        print(f"Total Trades:      {results['total_trades']}")
        print(f"Wins / Losses:     {results['wins']} / {results['losses']}")
        print(f"Win Rate:          {results['win_rate']:.1f}%")
        print(f"Profit Factor:     {results['profit_factor']:.2f}")
        print()
        print(f"Avg Win:           ${results['avg_win']:,.2f}")
        print(f"Avg Loss:          ${results['avg_loss']:,.2f}")
        print()
        print(f"Total Signals:     {results['total_signals']}")
        print(f"Actionable:        {results['actionable_signals']} ({results['actionable_signals']/results['total_signals']*100:.1f}%)")
        
        # Show trade log
        if results['trades']:
            print(f"\n📝 Trade Log:")
            print(f"{'Side':<6} {'Entry':<12} {'Exit':<12} {'PnL':<12} {'Reason':<12}")
            print("-" * 60)
            for t in results['trades'][-10:]:  # Last 10 trades
                print(f"{t['side']:<6} ${t['entry_price']:<10,.2f} ${t['exit_price']:<10,.2f} ${t['pnl']:<10,.2f} {t['reason']:<12}")


def main():
    parser = argparse.ArgumentParser(description='Backtest Trading Strategies')
    parser.add_argument('--pair', '-p', type=str, default='BTC', help='Trading pair')
    parser.add_argument('--candles', '-c', type=int, default=720, help='Number of candles')
    parser.add_argument('--interval', '-i', type=int, default=60, help='Candle interval (minutes)')
    parser.add_argument('--all', action='store_true', help='Test all pairs')
    parser.add_argument('--confidence', type=float, default=65, help='Min signal confidence')
    parser.add_argument('--sl', type=float, default=0.03, help='Stop loss %')
    parser.add_argument('--tp', type=float, default=0.05, help='Take profit %')
    
    args = parser.parse_args()
    
    print("🔬 SodaPoppy Strategy Backtester")
    print("=" * 60)
    
    backtester = Backtester(
        min_confidence=args.confidence,
        stop_loss_pct=args.sl,
        take_profit_pct=args.tp
    )
    
    pairs = list(PAIRS.keys()) if args.all else [args.pair]
    all_results = []
    
    for pair in pairs:
        candles = fetch_candles(pair, args.interval, args.candles)
        if candles is not None and len(candles) > 50:
            results = backtester.run(pair, candles)
            backtester.print_results(results)
            all_results.append(results)
    
    # Summary if multiple pairs
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("📈 OVERALL SUMMARY")
        print(f"{'='*60}")
        total_pnl = sum(r['total_pnl'] for r in all_results)
        total_trades = sum(r['total_trades'] for r in all_results)
        total_wins = sum(r['wins'] for r in all_results)
        print(f"Total PnL:     ${total_pnl:,.2f}")
        print(f"Total Trades:  {total_trades}")
        print(f"Overall Win%:  {total_wins/total_trades*100:.1f}%" if total_trades else "N/A")


if __name__ == '__main__':
    main()
