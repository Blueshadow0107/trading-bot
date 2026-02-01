"""
Jesse Backtest Runner for Kraken

This script runs backtests using Jesse's research API.
No web dashboard needed - pure Python.

Usage:
    python backtest_runner.py
"""

import numpy as np
from datetime import datetime, timedelta
from jesse.research import backtest, get_candles

# Import our strategies
import sys
sys.path.append('..')
# from strategies.rsi_mean_reversion import RSIMeanReversion
# from strategies.golden_cross import GoldenCross


def run_backtest():
    """Run a basic backtest."""
    
    # Configuration
    config = {
        'starting_balance': 10_000,  # $10k starting capital
        'fee': 0.0026,  # Kraken taker fee (0.26%)
        'type': 'spot',  # or 'futures'
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'exchange': 'Kraken',
        'warm_up_candles': 100
    }
    
    # Route: which strategy on which symbol/timeframe
    routes = [
        {
            'exchange': 'Kraken',
            'strategy': 'GoldenCross',  # Our strategy class name
            'symbol': 'BTC-USD',
            'timeframe': '4h'
        }
    ]
    
    # Data routes: additional data feeds
    data_routes = []
    
    # For now, we need to fetch/load candles
    # This is a placeholder - real implementation needs historical data
    print("📊 Backtest Configuration:")
    print(f"   Starting Balance: ${config['starting_balance']:,}")
    print(f"   Fee: {config['fee']*100}%")
    print(f"   Exchange: {config['exchange']}")
    print(f"   Symbol: {routes[0]['symbol']}")
    print(f"   Timeframe: {routes[0]['timeframe']}")
    print(f"   Strategy: {routes[0]['strategy']}")
    print()
    print("⚠️  To run actual backtest, need to:")
    print("   1. Import historical candle data")
    print("   2. Register strategy classes with Jesse")
    print("   3. Run: result = backtest(config, routes, data_routes, candles)")
    
    return config, routes


def fetch_kraken_candles(symbol='XXBTZUSD', interval=240, since=None):
    """
    Fetch historical candles from Kraken public API.
    
    Args:
        symbol: Kraken pair name (XXBTZUSD for BTC/USD)
        interval: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
        since: Unix timestamp to start from
    
    Returns:
        numpy array of candles
    """
    import requests
    
    url = f"https://api.kraken.com/0/public/OHLC"
    params = {
        'pair': symbol,
        'interval': interval,
    }
    if since:
        params['since'] = since
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data.get('error'):
        print(f"❌ Kraken API Error: {data['error']}")
        return None
    
    # Kraken returns: [time, open, high, low, close, vwap, volume, count]
    result = data['result']
    pair_key = [k for k in result.keys() if k != 'last'][0]
    candles = result[pair_key]
    
    # Convert to Jesse format: [timestamp, open, close, high, low, volume]
    jesse_candles = []
    for c in candles:
        jesse_candles.append([
            int(c[0]) * 1000,  # timestamp in ms
            float(c[1]),       # open
            float(c[4]),       # close
            float(c[2]),       # high
            float(c[3]),       # low
            float(c[6])        # volume
        ])
    
    return np.array(jesse_candles)


if __name__ == '__main__':
    print("🚀 Jesse Trading Bot - Kraken Backtester")
    print("=" * 50)
    print()
    
    # Run config check
    config, routes = run_backtest()
    
    print()
    print("📥 Fetching sample candles from Kraken...")
    candles = fetch_kraken_candles('XXBTZUSD', interval=240)  # 4h candles
    
    if candles is not None:
        print(f"✅ Fetched {len(candles)} candles")
        print(f"   Date range: {datetime.fromtimestamp(candles[0][0]/1000)} to {datetime.fromtimestamp(candles[-1][0]/1000)}")
        print(f"   Latest close: ${candles[-1][2]:,.2f}")
    
    print()
    print("📝 Next steps:")
    print("   1. Register strategies with Jesse")
    print("   2. Run full backtest with historical data")
    print("   3. Analyze results and optimize")
