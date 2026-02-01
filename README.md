# Trading Bot 🥤

Collaborative trading signal system built by AI agents (SodaPoppy + Vayu) with human oversight (Sripaad).

## Status
🚧 **Active Development** - Building in public

## Components

### Signal Engine (`signal_engine.py`)
Multi-strategy signal generator that combines:
- **RSI Mean Reversion** - Buy oversold, sell overbought
- **Golden Cross** - EMA crossover trend following  
- **MACD** - Momentum analysis

Each strategy produces a signal with confidence. The engine combines them using configurable weights.

```bash
# Test the signal engine
python3 signal_engine.py
```

### Paper Trader (`soda_paper_trader.py`)
Live paper trading bot that:
- Connects to Kraken public API
- Trades BTC/USD and ETH/USD
- Implements stop loss / take profit
- Persists state to JSON

```bash
# Run the paper trader
python3 soda_paper_trader.py
```

### Discord Alerts (`alerts/discord_alerts.py`)
Posts trading signals to Discord via webhook:
- Formatted embeds with colors
- Signal, price, RSI, confidence
- Trade open/close notifications

```bash
# Set webhook URL
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

# Test alerts
python3 -c "from alerts import send_alert; send_alert({'symbol': 'BTC/USD', 'side': 'LONG', 'price': 45000, 'rsi': 28})"
```

### Jesse Strategies (`strategies/`)
Strategies formatted for [Jesse.trade](https://jesse.trade) backtesting:
- `rsi_mean_reversion.py` - With hyperparameters for optimization
- `golden_cross.py` - Trend following

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Source   │────▶│  Signal Engine   │────▶│     Alerts      │
│  (Kraken API)   │     │  (Multi-strat)   │     │   (Discord)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Paper Trader    │
                        │  (Execution)     │
                        └──────────────────┘
```

## Setup

```bash
# Clone
git clone https://github.com/Sripaad/trading-bot.git
cd trading-bot

# Install deps
pip install requests numpy

# (Optional) For Jesse backtesting
pip install jesse

# Configure
export DISCORD_WEBHOOK_URL="your-webhook-url"
```

## Roadmap

- [x] Basic signal generation (RSI, BB, MACD, EMA)
- [x] Paper trading with Kraken
- [x] Discord alert system
- [ ] Multi-timeframe analysis
- [ ] Backtesting integration
- [ ] Meme coin support (DEX APIs)
- [ ] Forex data sources
- [ ] Risk management module
- [ ] Live trading (careful!)

## Contributing

This is a learning project. PRs welcome but expect chaos.

## Disclaimer

⚠️ **This is not financial advice.** Paper trading only. Don't use real money unless you know what you're doing.

## Contributors

- **SodaPoppy** - AI agent (signal engine, alerts)
- **Vayu** - AI agent (TBD)
- **Sripaad** - Human overseer
