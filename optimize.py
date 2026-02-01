#!/usr/bin/env python3
"""
Strategy Parameter Optimizer

Grid search over parameters to find optimal settings.

Usage:
    python3 optimize.py                     # Quick optimization
    python3 optimize.py --extensive         # More combinations
    python3 optimize.py --pair BTC          # Single pair
"""

import argparse
import itertools
from datetime import datetime
from typing import List, Dict, Any, Tuple
import requests
import numpy as np

from signal_engine import SignalEngine, SignalType


# Pair mapping
PAIRS = {
    'BTC': 'XXBTZUSD',
    'ETH': 'XETHZUSD',
}


def fetch_candles(pair: str, interval: int = 60, count: int = 720) -> np.ndarray:
    """Fetch historical candles from Kraken."""
    kraken_pair = PAIRS.get(pair, pair)
    url = "https://api.kraken.com/0/public/OHLC"
    params = {'pair': kraken_pair, 'interval': interval}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        result = data['result']
        pair_key = [k for k in result.keys() if k != 'last'][0]
        candles = result[pair_key][-count:]
        return np.array([
            [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])]
            for c in candles
        ])
    except Exception as e:
        print(f"❌ Error fetching {pair}: {e}")
        return None


def run_single_backtest(
    candles: np.ndarray,
    engine: SignalEngine,
    stop_loss_pct: float,
    take_profit_pct: float,
    min_confidence: float,
    position_size_pct: float = 0.10,
    starting_balance: float = 10000,
    lookback: int = 50
) -> Dict[str, Any]:
    """Run a single backtest with given parameters."""
    
    balance = starting_balance
    position = None
    trades = []
    
    for i in range(lookback, len(candles)):
        window = candles[i-lookback:i+1]
        current_price = candles[i, 4]
        
        # Check exit
        if position:
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
            if position['side'] == 'short':
                pnl_pct = -pnl_pct
            
            if pnl_pct <= -stop_loss_pct:
                pnl = (current_price - position['entry_price']) * position['qty']
                if position['side'] == 'short':
                    pnl = -pnl
                balance += pnl
                trades.append({'pnl': pnl, 'reason': 'sl'})
                position = None
            elif pnl_pct >= take_profit_pct:
                pnl = (current_price - position['entry_price']) * position['qty']
                if position['side'] == 'short':
                    pnl = -pnl
                balance += pnl
                trades.append({'pnl': pnl, 'reason': 'tp'})
                position = None
        
        # Check entry
        if not position:
            signal = engine.analyze('test', window)
            if signal.signal != SignalType.NEUTRAL and signal.confidence >= min_confidence:
                side = 'long' if signal.signal in [SignalType.LONG, SignalType.STRONG_LONG] else 'short'
                qty = (balance * position_size_pct) / current_price
                position = {
                    'side': side,
                    'entry_price': current_price,
                    'qty': qty
                }
    
    # Close remaining position
    if position:
        current_price = candles[-1, 4]
        pnl = (current_price - position['entry_price']) * position['qty']
        if position['side'] == 'short':
            pnl = -pnl
        balance += pnl
        trades.append({'pnl': pnl, 'reason': 'end'})
    
    total_pnl = balance - starting_balance
    total_pnl_pct = (total_pnl / starting_balance) * 100
    wins = len([t for t in trades if t['pnl'] > 0])
    
    return {
        'pnl': total_pnl,
        'pnl_pct': total_pnl_pct,
        'trades': len(trades),
        'wins': wins,
        'win_rate': wins / len(trades) * 100 if trades else 0,
        'final_balance': balance
    }


def optimize(
    pairs: List[str],
    sl_values: List[float],
    tp_values: List[float],
    conf_values: List[float],
    candle_count: int = 720
) -> List[Tuple[Dict, Dict]]:
    """
    Grid search optimization.
    
    Returns sorted list of (params, results) tuples.
    """
    print("🔬 Parameter Optimizer")
    print("=" * 60)
    
    # Fetch data
    pair_candles = {}
    for pair in pairs:
        print(f"📥 Fetching {pair} data...")
        candles = fetch_candles(pair, count=candle_count)
        if candles is not None:
            pair_candles[pair] = candles
    
    if not pair_candles:
        print("❌ No data fetched")
        return []
    
    # Generate combinations
    combinations = list(itertools.product(sl_values, tp_values, conf_values))
    total = len(combinations)
    print(f"\n🔄 Testing {total} parameter combinations...")
    
    engine = SignalEngine()
    results = []
    
    for idx, (sl, tp, conf) in enumerate(combinations):
        # Skip invalid combinations (TP should be > SL)
        if tp <= sl:
            continue
        
        # Run backtest for each pair and average
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        
        for pair, candles in pair_candles.items():
            result = run_single_backtest(
                candles, engine,
                stop_loss_pct=sl,
                take_profit_pct=tp,
                min_confidence=conf
            )
            total_pnl += result['pnl']
            total_trades += result['trades']
            total_wins += result['wins']
        
        avg_pnl_pct = (total_pnl / (10000 * len(pair_candles))) * 100
        win_rate = total_wins / total_trades * 100 if total_trades else 0
        
        params = {'sl': sl, 'tp': tp, 'conf': conf}
        result = {
            'pnl': total_pnl,
            'pnl_pct': avg_pnl_pct,
            'trades': total_trades,
            'win_rate': win_rate
        }
        
        results.append((params, result))
        
        # Progress
        if (idx + 1) % 20 == 0:
            print(f"   Progress: {idx+1}/{total}")
    
    # Sort by PnL
    results.sort(key=lambda x: x[1]['pnl'], reverse=True)
    
    return results


def print_results(results: List[Tuple[Dict, Dict]], top_n: int = 10):
    """Print top optimization results."""
    print(f"\n{'='*70}")
    print(f"🏆 TOP {top_n} PARAMETER COMBINATIONS")
    print(f"{'='*70}")
    print(f"{'Rank':<5} {'SL%':<6} {'TP%':<6} {'Conf':<6} {'PnL%':<10} {'Trades':<8} {'Win%':<8}")
    print("-" * 70)
    
    for i, (params, result) in enumerate(results[:top_n], 1):
        print(f"{i:<5} {params['sl']*100:<6.0f} {params['tp']*100:<6.0f} {params['conf']:<6.0f} {result['pnl_pct']:<10.2f} {result['trades']:<8} {result['win_rate']:<8.1f}")
    
    # Best result
    if results:
        best_params, best_result = results[0]
        print(f"\n✨ BEST: SL={best_params['sl']*100:.0f}%, TP={best_params['tp']*100:.0f}%, Conf={best_params['conf']:.0f}")
        print(f"   PnL: {best_result['pnl_pct']:.2f}% | Trades: {best_result['trades']} | Win: {best_result['win_rate']:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Optimize Strategy Parameters')
    parser.add_argument('--extensive', action='store_true', help='More combinations')
    parser.add_argument('--pair', type=str, help='Single pair to test')
    parser.add_argument('--candles', type=int, default=720, help='Number of candles')
    
    args = parser.parse_args()
    
    # Parameter ranges
    if args.extensive:
        sl_values = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10]
        tp_values = [0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
        conf_values = [60, 65, 70, 75, 80]
    else:
        sl_values = [0.03, 0.05, 0.07]
        tp_values = [0.05, 0.08, 0.12]
        conf_values = [65, 70, 75]
    
    pairs = [args.pair] if args.pair else ['BTC', 'ETH']
    
    results = optimize(pairs, sl_values, tp_values, conf_values, args.candles)
    print_results(results)


if __name__ == '__main__':
    main()
