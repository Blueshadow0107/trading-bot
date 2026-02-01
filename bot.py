#!/usr/bin/env python3
"""
SodaPoppy Trading Bot - Unified Runner

Combines signal engine, paper trading, and Discord alerts into one system.

Usage:
    python3 bot.py                    # Run with defaults
    python3 bot.py --live-alerts      # Enable Discord alerts
    python3 bot.py --pairs BTC ETH    # Specify pairs
    python3 bot.py --interval 300     # Check every 5 min
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Dict, Any

import requests
import numpy as np

from signal_engine import SignalEngine, SignalType, CompositeSignal
from alerts.discord_alerts import DiscordAlerts


# Kraken pair mapping
PAIR_MAP = {
    'BTC': 'XXBTZUSD',
    'ETH': 'XETHZUSD',
    'SOL': 'SOLUSD',
    'XRP': 'XXRPZUSD',
    'ADA': 'ADAUSD',
    'DOGE': 'XDGUSD',
    'DOT': 'DOTUSD',
    'LINK': 'LINKUSD',
}


class TradingBot:
    """Unified trading bot with signals, paper trading, and alerts."""
    
    def __init__(
        self,
        pairs: list = None,
        starting_balance: float = 10000,
        position_size_pct: float = 0.05,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.05,
        enable_alerts: bool = False,
        webhook_url: str = None
    ):
        self.pairs = pairs or ['BTC', 'ETH']
        self.starting_balance = starting_balance
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        # Components
        self.signal_engine = SignalEngine()
        self.alerter = DiscordAlerts(webhook_url) if enable_alerts else None
        
        # State
        self.state = {
            'balance': starting_balance,
            'positions': {},
            'trades': [],
            'signals_generated': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # Load existing state if available
        self._load_state()
    
    def _load_state(self):
        """Load state from file if exists."""
        try:
            with open('bot_state.json', 'r') as f:
                saved = json.load(f)
                self.state['balance'] = saved.get('balance', self.starting_balance)
                self.state['positions'] = saved.get('positions', {})
                self.state['trades'] = saved.get('trades', [])
        except FileNotFoundError:
            pass
    
    def _save_state(self):
        """Save state to file."""
        with open('bot_state.json', 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def fetch_candles(self, pair: str, interval: int = 60, count: int = 100) -> np.ndarray:
        """Fetch candles from Kraken."""
        kraken_pair = PAIR_MAP.get(pair, pair)
        url = "https://api.kraken.com/0/public/OHLC"
        params = {'pair': kraken_pair, 'interval': interval}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('error') and len(data['error']) > 0:
                print(f"  ❌ Kraken error for {pair}: {data['error']}")
                return None
            
            result = data['result']
            pair_key = [k for k in result.keys() if k != 'last'][0]
            candles = result[pair_key][-count:]
            
            return np.array([
                [float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6])]
                for c in candles
            ])
        except Exception as e:
            print(f"  ❌ Fetch error for {pair}: {e}")
            return None
    
    def check_exits(self):
        """Check stop loss and take profit for open positions."""
        for pair, pos in list(self.state['positions'].items()):
            candles = self.fetch_candles(pair, count=5)
            if candles is None:
                continue
            
            current_price = candles[-1, 4]
            entry_price = pos['entry_price']
            side = pos['side']
            
            pnl_pct = (current_price - entry_price) / entry_price
            if side == 'short':
                pnl_pct = -pnl_pct
            
            if pnl_pct <= -self.stop_loss_pct:
                print(f"  🛑 STOP LOSS: {pair} @ ${current_price:,.2f} ({pnl_pct*100:.1f}%)")
                self._close_position(pair, current_price, 'stop_loss')
            elif pnl_pct >= self.take_profit_pct:
                print(f"  💰 TAKE PROFIT: {pair} @ ${current_price:,.2f} ({pnl_pct*100:+.1f}%)")
                self._close_position(pair, current_price, 'take_profit')
    
    def _close_position(self, pair: str, exit_price: float, reason: str):
        """Close a position and update state."""
        pos = self.state['positions'].pop(pair)
        
        pnl = (exit_price - pos['entry_price']) * pos['qty']
        if pos['side'] == 'short':
            pnl = -pnl
        
        self.state['balance'] += pnl
        
        trade_record = {
            **pos,
            'exit_price': exit_price,
            'exit_time': datetime.now().isoformat(),
            'pnl': pnl,
            'reason': reason
        }
        self.state['trades'].append(trade_record)
        
        print(f"  📊 Closed {pair}: PnL ${pnl:,.2f} | Balance: ${self.state['balance']:,.2f}")
        
        # Alert if enabled
        if self.alerter:
            self.alerter.send_trade_closed(
                pair, pos['side'], pos['entry_price'], exit_price, pnl
            )
        
        self._save_state()
    
    def execute_signal(self, pair: str, signal: CompositeSignal):
        """Execute a trade based on signal."""
        # Only trade on actionable signals with high confidence
        if signal.signal in [SignalType.NEUTRAL]:
            return
        
        if signal.confidence < 65:
            print(f"  ⏸️  Signal confidence too low ({signal.confidence:.0f}%)")
            return
        
        if pair in self.state['positions']:
            print(f"  ⏸️  Already have position in {pair}")
            return
        
        # Determine side
        if signal.signal in [SignalType.LONG, SignalType.STRONG_LONG]:
            side = 'long'
        else:
            side = 'short'
        
        # Calculate position
        position_value = self.state['balance'] * self.position_size_pct
        qty = position_value / signal.price
        
        # Open position
        self.state['positions'][pair] = {
            'entry_price': signal.price,
            'qty': qty,
            'side': side,
            'entry_time': datetime.now().isoformat(),
            'signal_confidence': signal.confidence
        }
        
        print(f"  🎯 PAPER TRADE: {side.upper()} {pair} @ ${signal.price:,.2f} (qty: {qty:.6f})")
        
        # Alert if enabled
        if self.alerter:
            alert_data = signal.to_alert_dict()
            alert_data['stop_loss'] = signal.price * (1 - self.stop_loss_pct) if side == 'long' else signal.price * (1 + self.stop_loss_pct)
            alert_data['take_profit'] = signal.price * (1 + self.take_profit_pct) if side == 'long' else signal.price * (1 - self.take_profit_pct)
            self.alerter.send_signal(alert_data)
        
        self._save_state()
    
    def scan(self):
        """Scan all pairs for signals."""
        print(f"\n{'='*60}")
        print(f"🥤 SodaPoppy Bot — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        print(f"💰 Balance: ${self.state['balance']:,.2f}")
        print(f"📈 Positions: {len(self.state['positions'])}")
        print(f"🔄 Total Trades: {len(self.state['trades'])}")
        print()
        
        # Check exits first
        if self.state['positions']:
            print("📊 Checking exits...")
            self.check_exits()
            print()
        
        # Scan for new signals
        print("📡 Scanning pairs...")
        for pair in self.pairs:
            candles = self.fetch_candles(pair)
            if candles is None:
                continue
            
            signal = self.signal_engine.analyze(pair, candles)
            self.state['signals_generated'] += 1
            
            signal_emoji = {
                SignalType.STRONG_LONG: "🟢🟢",
                SignalType.LONG: "🟢",
                SignalType.NEUTRAL: "⚪",
                SignalType.SHORT: "🔴",
                SignalType.STRONG_SHORT: "🔴🔴"
            }
            
            print(f"  {pair}/USD: ${signal.price:,.2f} {signal_emoji[signal.signal]} {signal.signal.name} ({signal.confidence:.0f}%)")
            
            # Execute if actionable
            if signal.signal != SignalType.NEUTRAL:
                self.execute_signal(pair, signal)
        
        self._save_state()
    
    def run(self, interval: int = 60):
        """Main loop."""
        print("🚀 Starting SodaPoppy Trading Bot")
        print(f"   Pairs: {', '.join(self.pairs)}")
        print(f"   Check interval: {interval}s")
        print(f"   Alerts: {'ON' if self.alerter else 'OFF'}")
        print()
        
        try:
            while True:
                self.scan()
                print(f"\n⏳ Next scan in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 Bot stopped")
            self._print_summary()
    
    def _print_summary(self):
        """Print final summary."""
        initial = self.starting_balance
        final = self.state['balance']
        pnl = final - initial
        pnl_pct = (pnl / initial) * 100
        
        print(f"\n{'='*60}")
        print("📊 SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Starting Balance: ${initial:,.2f}")
        print(f"Final Balance:    ${final:,.2f}")
        print(f"Total PnL:        ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"Total Trades:     {len(self.state['trades'])}")
        print(f"Signals Generated: {self.state['signals_generated']}")
        
        if self.state['trades']:
            wins = sum(1 for t in self.state['trades'] if t.get('pnl', 0) > 0)
            losses = len(self.state['trades']) - wins
            print(f"Win Rate:         {wins}/{len(self.state['trades'])} ({wins/len(self.state['trades'])*100:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description='SodaPoppy Trading Bot')
    parser.add_argument('--pairs', nargs='+', default=['BTC', 'ETH'], help='Pairs to trade')
    parser.add_argument('--interval', type=int, default=60, help='Scan interval in seconds')
    parser.add_argument('--balance', type=float, default=10000, help='Starting balance')
    parser.add_argument('--live-alerts', action='store_true', help='Enable Discord alerts')
    parser.add_argument('--webhook', type=str, help='Discord webhook URL')
    parser.add_argument('--scan-once', action='store_true', help='Scan once and exit')
    
    args = parser.parse_args()
    
    bot = TradingBot(
        pairs=args.pairs,
        starting_balance=args.balance,
        enable_alerts=args.live_alerts,
        webhook_url=args.webhook
    )
    
    if args.scan_once:
        bot.scan()
    else:
        bot.run(interval=args.interval)


if __name__ == '__main__':
    main()
