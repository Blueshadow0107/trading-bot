#!/usr/bin/env python3
"""
Live Signal Test - Real-time BTC/ETH signals using v2 detector
Fetches live data from CoinGecko and generates signals
"""

import requests
import numpy as np
import json
from datetime import datetime
from core.regime_detector_v2 import analyze_market_v2, generate_signal, format_signal_log

COINGECKO_API = "https://api.coingecko.com/api/v3"

def fetch_ohlcv(coin_id: str, days: int = 90) -> dict:
    """Fetch OHLCV data from CoinGecko."""
    url = f"{COINGECKO_API}/coins/{coin_id}/ohlc"
    params = {
        "vs_currency": "usd",
        "days": days
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # CoinGecko OHLC format: [timestamp, open, high, low, close]
        timestamps = [d[0] for d in data]
        opens = np.array([d[1] for d in data])
        highs = np.array([d[2] for d in data])
        lows = np.array([d[3] for d in data])
        closes = np.array([d[4] for d in data])
        
        return {
            "timestamps": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes
        }
    except Exception as e:
        print(f"Error fetching {coin_id}: {e}")
        return None


def fetch_current_price(coin_id: str) -> dict:
    """Fetch current price and 24h volume."""
    url = f"{COINGECKO_API}/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_vol": "true",
        "include_24hr_change": "true"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return {
            "price": data[coin_id]["usd"],
            "volume_24h": data[coin_id]["usd_24h_vol"],
            "change_24h": data[coin_id]["usd_24h_change"]
        }
    except Exception as e:
        print(f"Error fetching price for {coin_id}: {e}")
        return None


def analyze_coin(coin_id: str, symbol: str):
    """Full analysis for a single coin."""
    print(f"\n{'='*60}")
    print(f"📊 Analyzing {symbol}...")
    print(f"{'='*60}")
    
    # Fetch OHLCV data
    ohlcv = fetch_ohlcv(coin_id, days=90)
    if not ohlcv:
        print(f"❌ Failed to fetch OHLCV data for {symbol}")
        return None
    
    # Fetch current price
    current = fetch_current_price(coin_id)
    if not current:
        print(f"❌ Failed to fetch current price for {symbol}")
        return None
    
    # Create volume array (approximate from 24h volume)
    # CoinGecko OHLC doesn't include volume, so we estimate
    volume = np.ones(len(ohlcv["close"])) * current["volume_24h"] / 24
    
    # Run analysis
    state = analyze_market_v2(
        ohlcv["high"],
        ohlcv["low"], 
        ohlcv["close"],
        volume,
        symbol
    )
    
    signal = generate_signal(state)
    
    # Display results
    print(f"\n💰 Current Price: ${current['price']:,.2f} ({current['change_24h']:+.2f}% 24h)")
    print(f"📈 24h Volume: ${current['volume_24h']:,.0f}")
    
    print(f"\n📊 Technical Indicators:")
    print(f"   RSI-7:  {state.rsi_7:>6.2f}  |  RSI-14: {state.rsi_14:>6.2f}")
    print(f"   ADX:    {state.adx:>6.2f}  |  MACD:   {state.macd:>+.4f}")
    print(f"   ATR:    ${state.atr_14:>,.2f} ({state.atr_percent:.2f}%)")
    print(f"   Vol Ratio: {state.volume_ratio:.2f}x average")
    
    print(f"\n🎯 Regime Detection:")
    print(f"   Regime:   {state.regime}")
    print(f"   Strategy: {state.strategy}")
    print(f"   Position: {state.position_size_multiplier}x")
    
    # Signal with color coding (terminal)
    action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}
    print(f"\n🚦 SIGNAL: {action_emoji.get(signal['action'], '⚪')} {signal['action']}")
    print(f"   Confidence: {signal['confidence']}%")
    print(f"   Reasoning: {signal['reasoning']}")
    
    # Log format
    print(f"\n📝 Log: {format_signal_log(signal, symbol)}")
    
    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "price": current["price"],
        "change_24h": current["change_24h"],
        "state": {
            "regime": state.regime,
            "strategy": state.strategy,
            "rsi_7": state.rsi_7,
            "rsi_14": state.rsi_14,
            "adx": state.adx,
            "macd": state.macd,
            "atr_percent": state.atr_percent,
            "position_size": state.position_size_multiplier
        },
        "signal": signal
    }


def main():
    print("=" * 60)
    print("🔬 LIVE SIGNAL TEST - Regime Detector v2")
    print(f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)
    
    coins = [
        ("bitcoin", "BTC/USD"),
        ("ethereum", "ETH/USD"),
    ]
    
    results = []
    for coin_id, symbol in coins:
        result = analyze_coin(coin_id, symbol)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    for r in results:
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}
        print(f"{r['symbol']}: {action_emoji.get(r['signal']['action'], '⚪')} {r['signal']['action']} "
              f"({r['signal']['confidence']}%) | {r['state']['regime']} | ${r['price']:,.2f}")
    
    # Save to file
    output_file = f"logs/live_signal_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results
        }, f, indent=2)
    print(f"\n💾 Saved to {output_file}")
    
    return results


if __name__ == "__main__":
    main()
