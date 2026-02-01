"""
Kraken Exchange Configuration for Jesse.trade

IMPORTANT: 
- Never commit API keys to git!
- Use .env file or environment variables
- Start with paper trading before live!
"""

import os

# Exchange configuration
KRAKEN_CONFIG = {
    'name': 'Kraken',
    'api_key': os.getenv('KRAKEN_API_KEY', ''),
    'api_secret': os.getenv('KRAKEN_API_SECRET', ''),
    
    # Trading pairs to monitor
    'symbols': [
        'BTC-USD',
        'ETH-USD', 
        'SOL-USD',
    ],
    
    # Timeframes for analysis
    'timeframes': ['1h', '4h', '1D'],
    
    # Risk parameters
    'max_position_size_pct': 0.05,  # 5% of portfolio per trade
    'max_open_positions': 3,
    'default_leverage': 1,  # No leverage by default (safer)
}

# Rate limits (Kraken specifics)
RATE_LIMITS = {
    'public': {
        'calls_per_second': 1,
        'calls_per_minute': 60,
    },
    'private': {
        'calls_per_second': 0.5,
        'calls_per_minute': 15,  # Conservative for trading
    },
}

# Supported order types on Kraken
ORDER_TYPES = [
    'market',
    'limit',
    'stop-loss',
    'take-profit',
    'stop-loss-limit',
    'take-profit-limit',
    'trailing-stop',
]

# Minimum order sizes (approximate, check Kraken docs)
MIN_ORDER_SIZES = {
    'BTC-USD': 0.0001,
    'ETH-USD': 0.001,
    'SOL-USD': 0.1,
}

# Fee structure (maker/taker, varies by volume tier)
FEES = {
    'maker': 0.0016,  # 0.16% for low volume
    'taker': 0.0026,  # 0.26% for low volume
}


def get_kraken_config():
    """Return validated Kraken configuration."""
    if not KRAKEN_CONFIG['api_key'] or not KRAKEN_CONFIG['api_secret']:
        print("⚠️  WARNING: Kraken API keys not set!")
        print("   Set KRAKEN_API_KEY and KRAKEN_API_SECRET environment variables")
        print("   Or edit this file (not recommended for production)")
    
    return KRAKEN_CONFIG


def validate_symbol(symbol: str) -> bool:
    """Check if symbol is supported."""
    return symbol in KRAKEN_CONFIG['symbols']


# API endpoints reference
KRAKEN_ENDPOINTS = {
    'base_url': 'https://api.kraken.com',
    'futures_url': 'https://futures.kraken.com',
    
    # Public endpoints
    'ticker': '/0/public/Ticker',
    'ohlc': '/0/public/OHLC',
    'orderbook': '/0/public/Depth',
    'trades': '/0/public/Trades',
    
    # Private endpoints
    'balance': '/0/private/Balance',
    'open_orders': '/0/private/OpenOrders',
    'add_order': '/0/private/AddOrder',
    'cancel_order': '/0/private/CancelOrder',
    'positions': '/0/private/OpenPositions',
}
