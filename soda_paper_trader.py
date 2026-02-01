"""
SodaPoppy Paper Trading Bot - Mean Reversion Strategy

Strategy: RSI + Bollinger Bands Mean Reversion
- Buy: RSI < 30 AND price < lower BB
- Sell: RSI > 70 AND price > upper BB

Paper trading only - no real money.
"""

import requests
import numpy as np
import time
from datetime import datetime
import json

# Configuration
CONFIG = {
    'pairs': ['XXBTZUSD', 'XETHZUSD'],  # BTC/USD, ETH/USD
    'interval': 60,  # 1h candles
    'check_interval': 60,  # Check every 60 seconds
    'starting_balance': 10000,
    'position_size_pct': 0.05,  # 5% per trade
    'rsi_period': 14,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'bb_period': 20,
    'bb_std': 2,
    'stop_loss_pct': 0.05,
    'take_profit_pct': 0.05,
}

# State
state = {
    'balance': CONFIG['starting_balance'],
    'positions': {},  # {symbol: {'entry_price': x, 'qty': y, 'side': 'long'/'short'}}
    'trades': [],
    'start_time': datetime.now().isoformat(),
}


def fetch_candles(symbol, interval=60, count=100):
    """Fetch candles from Kraken public API."""
    url = "https://api.kraken.com/0/public/OHLC"
    params = {'pair': symbol, 'interval': interval}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('error') and len(data['error']) > 0:
            print(f"  ❌ Kraken API Error: {data['error']}")
            return None
        
        result = data['result']
        pair_key = [k for k in result.keys() if k != 'last'][0]
        candles = result[pair_key][-count:]
        
        # Convert to numpy: [time, open, high, low, close, volume]
        return np.array([[float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])] for c in candles])
    except Exception as e:
        print(f"  ❌ Fetch error: {e}")
        return None


def calculate_rsi(closes, period=14):
    """Calculate RSI."""
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_bollinger_bands(closes, period=20, std=2):
    """Calculate Bollinger Bands."""
    sma = np.mean(closes[-period:])
    std_dev = np.std(closes[-period:])
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower


def check_signals(symbol, candles):
    """Check for mean reversion signals."""
    closes = candles[:, 4]  # Close prices
    current_price = closes[-1]
    
    rsi = calculate_rsi(closes, CONFIG['rsi_period'])
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(closes, CONFIG['bb_period'], CONFIG['bb_std'])
    
    signal = None
    
    # Mean reversion: buy oversold, sell overbought
    if rsi < CONFIG['rsi_oversold'] and current_price < bb_lower:
        signal = 'LONG'
    elif rsi > CONFIG['rsi_overbought'] and current_price > bb_upper:
        signal = 'SHORT'
    
    return {
        'symbol': symbol,
        'price': current_price,
        'rsi': round(rsi, 2),
        'bb_upper': round(bb_upper, 2),
        'bb_lower': round(bb_lower, 2),
        'signal': signal
    }


def execute_paper_trade(signal_data):
    """Execute a paper trade."""
    symbol = signal_data['symbol']
    price = signal_data['price']
    signal = signal_data['signal']
    
    if symbol in state['positions']:
        print(f"  ⏸️  Already have position in {symbol}")
        return
    
    position_value = state['balance'] * CONFIG['position_size_pct']
    qty = position_value / price
    
    state['positions'][symbol] = {
        'entry_price': price,
        'qty': qty,
        'side': signal.lower(),
        'entry_time': datetime.now().isoformat()
    }
    
    trade = {
        'symbol': symbol,
        'side': signal,
        'entry_price': price,
        'qty': qty,
        'time': datetime.now().isoformat()
    }
    state['trades'].append(trade)
    
    print(f"  🎯 PAPER TRADE: {signal} {symbol} @ ${price:,.2f} (qty: {qty:.6f})")


def check_exits():
    """Check stop loss and take profit for open positions."""
    for symbol, pos in list(state['positions'].items()):
        candles = fetch_candles(symbol, CONFIG['interval'], 10)
        if candles is None:
            continue
        
        current_price = candles[-1, 4]
        entry_price = pos['entry_price']
        side = pos['side']
        
        pnl_pct = (current_price - entry_price) / entry_price
        if side == 'short':
            pnl_pct = -pnl_pct
        
        # Check stop loss or take profit
        if pnl_pct <= -CONFIG['stop_loss_pct']:
            print(f"  🛑 STOP LOSS: {symbol} @ ${current_price:,.2f} (PnL: {pnl_pct*100:.2f}%)")
            close_position(symbol, current_price, 'stop_loss')
        elif pnl_pct >= CONFIG['take_profit_pct']:
            print(f"  💰 TAKE PROFIT: {symbol} @ ${current_price:,.2f} (PnL: {pnl_pct*100:.2f}%)")
            close_position(symbol, current_price, 'take_profit')


def close_position(symbol, exit_price, reason):
    """Close a position."""
    pos = state['positions'].pop(symbol)
    
    pnl = (exit_price - pos['entry_price']) * pos['qty']
    if pos['side'] == 'short':
        pnl = -pnl
    
    state['balance'] += pnl
    
    print(f"  📊 Closed {symbol}: PnL ${pnl:,.2f} | New Balance: ${state['balance']:,.2f}")


def print_status():
    """Print current bot status."""
    print(f"\n{'='*60}")
    print(f"🥤 SodaPoppy Mean Reversion Bot - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    print(f"💰 Balance: ${state['balance']:,.2f}")
    print(f"📈 Open Positions: {len(state['positions'])}")
    print(f"📊 Total Trades: {len(state['trades'])}")
    print()


def run_bot():
    """Main bot loop."""
    print("🚀 Starting SodaPoppy Paper Trading Bot")
    print(f"   Strategy: Mean Reversion (RSI + Bollinger Bands)")
    print(f"   Pairs: {CONFIG['pairs']}")
    print(f"   Starting Balance: ${CONFIG['starting_balance']:,}")
    print()
    
    while True:
        try:
            print_status()
            
            # Check exits first
            check_exits()
            
            # Check for new signals
            for pair in CONFIG['pairs']:
                print(f"  📡 Scanning {pair}...")
                candles = fetch_candles(pair, CONFIG['interval'])
                
                if candles is None:
                    continue
                
                signal_data = check_signals(pair, candles)
                
                print(f"     Price: ${signal_data['price']:,.2f} | RSI: {signal_data['rsi']} | BB: [{signal_data['bb_lower']:,.0f} - {signal_data['bb_upper']:,.0f}]")
                
                if signal_data['signal']:
                    print(f"  🔔 SIGNAL: {signal_data['signal']}!")
                    execute_paper_trade(signal_data)
            
            # Save state
            with open('soda_paper_state.json', 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"\n  ⏳ Next check in {CONFIG['check_interval']}s...")
            time.sleep(CONFIG['check_interval'])
            
        except KeyboardInterrupt:
            print("\n\n🛑 Bot stopped by user")
            print(f"Final Balance: ${state['balance']:,.2f}")
            print(f"Total Trades: {len(state['trades'])}")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)


if __name__ == '__main__':
    run_bot()
