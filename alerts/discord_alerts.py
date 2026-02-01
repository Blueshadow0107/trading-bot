"""
Discord Alert System for Trading Signals

Posts trading signals to Discord channels via webhook.
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any


class DiscordAlerts:
    """Send trading alerts to Discord via webhook."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord alerter.
        
        Args:
            webhook_url: Discord webhook URL. Falls back to DISCORD_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
        self.history = []
        
    def _format_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Format signal as Discord embed."""
        
        is_long = signal.get('side', '').upper() in ['LONG', 'BUY']
        color = 0x00ff00 if is_long else 0xff0000  # Green for long, red for short
        emoji = "🟢" if is_long else "🔴"
        
        embed = {
            "title": f"{emoji} {signal.get('side', 'SIGNAL').upper()} - {signal.get('symbol', 'UNKNOWN')}",
            "color": color,
            "fields": [
                {
                    "name": "💰 Price",
                    "value": f"${signal.get('price', 0):,.2f}",
                    "inline": True
                },
                {
                    "name": "📊 RSI",
                    "value": f"{signal.get('rsi', 'N/A')}",
                    "inline": True
                },
                {
                    "name": "📈 Strategy",
                    "value": signal.get('strategy', 'Mean Reversion'),
                    "inline": True
                }
            ],
            "footer": {
                "text": f"🥤 SodaPoppy Trading Bot • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        # Add optional fields
        if 'stop_loss' in signal:
            embed['fields'].append({
                "name": "🛑 Stop Loss",
                "value": f"${signal['stop_loss']:,.2f}",
                "inline": True
            })
        
        if 'take_profit' in signal:
            embed['fields'].append({
                "name": "💎 Take Profit",
                "value": f"${signal['take_profit']:,.2f}",
                "inline": True
            })
        
        if 'confidence' in signal:
            embed['fields'].append({
                "name": "🎯 Confidence",
                "value": f"{signal['confidence']}%",
                "inline": True
            })
        
        return embed
    
    def send_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Send a trading signal to Discord.
        
        Args:
            signal: Dict with keys: symbol, side, price, rsi, strategy, etc.
        
        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.webhook_url:
            print("⚠️  No Discord webhook URL configured")
            return False
        
        embed = self._format_signal(signal)
        
        payload = {
            "username": "SodaPoppy Trading Bot",
            "avatar_url": "https://em-content.zobj.net/source/twitter/376/cup-with-straw_1f964.png",
            "embeds": [embed]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 204]:
                self.history.append({
                    **signal,
                    'sent_at': datetime.now().isoformat(),
                    'status': 'sent'
                })
                return True
            else:
                print(f"❌ Discord webhook error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending to Discord: {e}")
            return False
    
    def send_status_update(self, balance: float, open_positions: int, total_trades: int) -> bool:
        """Send a status update embed."""
        if not self.webhook_url:
            return False
        
        embed = {
            "title": "📊 Bot Status Update",
            "color": 0x7289da,
            "fields": [
                {
                    "name": "💰 Balance",
                    "value": f"${balance:,.2f}",
                    "inline": True
                },
                {
                    "name": "📈 Open Positions",
                    "value": str(open_positions),
                    "inline": True
                },
                {
                    "name": "🔄 Total Trades",
                    "value": str(total_trades),
                    "inline": True
                }
            ],
            "footer": {
                "text": f"🥤 SodaPoppy • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        payload = {
            "username": "SodaPoppy Trading Bot",
            "embeds": [embed]
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code in [200, 204]
        except:
            return False
    
    def send_trade_closed(self, symbol: str, side: str, entry: float, exit: float, pnl: float) -> bool:
        """Send trade closed notification."""
        if not self.webhook_url:
            return False
        
        is_profit = pnl >= 0
        color = 0x00ff00 if is_profit else 0xff0000
        emoji = "💰" if is_profit else "📉"
        pnl_pct = ((exit - entry) / entry) * 100
        if side.upper() == 'SHORT':
            pnl_pct = -pnl_pct
        
        embed = {
            "title": f"{emoji} Trade Closed - {symbol}",
            "color": color,
            "fields": [
                {"name": "Side", "value": side.upper(), "inline": True},
                {"name": "Entry", "value": f"${entry:,.2f}", "inline": True},
                {"name": "Exit", "value": f"${exit:,.2f}", "inline": True},
                {"name": "PnL", "value": f"${pnl:,.2f} ({pnl_pct:+.2f}%)", "inline": True}
            ],
            "footer": {
                "text": f"🥤 SodaPoppy • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        payload = {"username": "SodaPoppy Trading Bot", "embeds": [embed]}
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            return response.status_code in [200, 204]
        except:
            return False


# Convenience function for quick alerts
def send_alert(signal: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """Quick function to send a single alert."""
    alerter = DiscordAlerts(webhook_url)
    return alerter.send_signal(signal)


if __name__ == '__main__':
    # Test with example signal
    test_signal = {
        'symbol': 'BTC/USD',
        'side': 'LONG',
        'price': 45000.00,
        'rsi': 28.5,
        'strategy': 'RSI Mean Reversion',
        'stop_loss': 42750.00,
        'take_profit': 47250.00,
        'confidence': 75
    }
    
    alerter = DiscordAlerts()
    
    if alerter.webhook_url:
        print("Sending test signal...")
        success = alerter.send_signal(test_signal)
        print(f"Result: {'✅ Sent!' if success else '❌ Failed'}")
    else:
        print("⚠️  Set DISCORD_WEBHOOK_URL environment variable to test")
        print("\nExample embed that would be sent:")
        print(json.dumps(alerter._format_signal(test_signal), indent=2))
