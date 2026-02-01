"""
DexScreener API Client

Fetches meme coin / DEX token data from DexScreener.
Free API, no auth required.

Docs: https://docs.dexscreener.com/api/reference
"""

import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TokenPair:
    """Represents a trading pair from DexScreener."""
    chain: str
    dex: str
    pair_address: str
    base_token: Dict[str, str]  # {address, name, symbol}
    quote_token: Dict[str, str]
    price_usd: float
    price_change_5m: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    fdv: Optional[float]  # Fully diluted valuation
    txns_24h: Dict[str, int]  # {buys, sells}
    url: str
    
    @property
    def symbol(self) -> str:
        return f"{self.base_token['symbol']}/{self.quote_token['symbol']}"
    
    @property
    def buy_sell_ratio(self) -> float:
        """Ratio of buys to sells (>1 = more buying)."""
        buys = self.txns_24h.get('buys', 0)
        sells = self.txns_24h.get('sells', 0)
        if sells == 0:
            return float('inf') if buys > 0 else 1.0
        return buys / sells
    
    def is_bullish(self) -> bool:
        """Simple bullish signal based on price action and volume."""
        return (
            self.price_change_1h > 0 and
            self.price_change_24h > 0 and
            self.buy_sell_ratio > 1.2
        )


class DexScreener:
    """Client for DexScreener API."""
    
    BASE_URL = "https://api.dexscreener.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'SodaPoppy-TradingBot/1.0'
        })
    
    def _get(self, endpoint: str) -> Optional[Dict]:
        """Make GET request to DexScreener API."""
        try:
            response = self.session.get(f"{self.BASE_URL}{endpoint}", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ DexScreener API error: {e}")
            return None
    
    def _parse_pair(self, data: Dict) -> Optional[TokenPair]:
        """Parse API response into TokenPair object."""
        try:
            return TokenPair(
                chain=data.get('chainId', ''),
                dex=data.get('dexId', ''),
                pair_address=data.get('pairAddress', ''),
                base_token=data.get('baseToken', {}),
                quote_token=data.get('quoteToken', {}),
                price_usd=float(data.get('priceUsd', 0) or 0),
                price_change_5m=float(data.get('priceChange', {}).get('m5', 0) or 0),
                price_change_1h=float(data.get('priceChange', {}).get('h1', 0) or 0),
                price_change_6h=float(data.get('priceChange', {}).get('h6', 0) or 0),
                price_change_24h=float(data.get('priceChange', {}).get('h24', 0) or 0),
                volume_24h=float(data.get('volume', {}).get('h24', 0) or 0),
                liquidity_usd=float(data.get('liquidity', {}).get('usd', 0) or 0),
                fdv=float(data.get('fdv', 0) or 0) if data.get('fdv') else None,
                txns_24h={
                    'buys': data.get('txns', {}).get('h24', {}).get('buys', 0),
                    'sells': data.get('txns', {}).get('h24', {}).get('sells', 0)
                },
                url=data.get('url', '')
            )
        except Exception as e:
            print(f"⚠️ Failed to parse pair: {e}")
            return None
    
    def search_tokens(self, query: str) -> List[TokenPair]:
        """
        Search for tokens by name or symbol.
        
        Args:
            query: Token name or symbol (e.g., "PEPE", "BONK")
        
        Returns:
            List of matching TokenPairs
        """
        data = self._get(f"/latest/dex/search?q={query}")
        if not data or 'pairs' not in data:
            return []
        
        pairs = []
        for pair_data in data['pairs'][:20]:  # Limit to top 20
            pair = self._parse_pair(pair_data)
            if pair:
                pairs.append(pair)
        
        return pairs
    
    def get_token_pairs(self, chain: str, token_address: str) -> List[TokenPair]:
        """
        Get all pairs for a specific token.
        
        Args:
            chain: Chain ID (e.g., "solana", "ethereum", "bsc")
            token_address: Token contract address
        
        Returns:
            List of TokenPairs
        """
        data = self._get(f"/latest/dex/tokens/{token_address}")
        if not data or 'pairs' not in data:
            return []
        
        pairs = []
        for pair_data in data['pairs']:
            if pair_data.get('chainId') == chain or chain == 'all':
                pair = self._parse_pair(pair_data)
                if pair:
                    pairs.append(pair)
        
        return pairs
    
    def get_trending(self, chain: str = 'solana') -> List[TokenPair]:
        """
        Get trending/top pairs by volume.
        
        Note: DexScreener doesn't have a direct trending endpoint,
        so we search for popular meme coins and sort by volume.
        """
        # Popular meme coin tickers to scan
        meme_tickers = ['PEPE', 'BONK', 'WIF', 'BOME', 'POPCAT', 'MEW', 'GIGA']
        
        all_pairs = []
        for ticker in meme_tickers:
            pairs = self.search_tokens(ticker)
            # Filter by chain and liquidity
            for pair in pairs:
                if pair.chain == chain and pair.liquidity_usd > 50000:
                    all_pairs.append(pair)
        
        # Sort by 24h volume
        all_pairs.sort(key=lambda p: p.volume_24h, reverse=True)
        
        # Remove duplicates (same pair address)
        seen = set()
        unique = []
        for p in all_pairs:
            if p.pair_address not in seen:
                seen.add(p.pair_address)
                unique.append(p)
        
        return unique[:10]
    
    def analyze_token(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Quick analysis of a meme coin.
        
        Returns analysis dict with signal.
        """
        pairs = self.search_tokens(query)
        if not pairs:
            return None
        
        # Get highest liquidity pair
        pair = max(pairs, key=lambda p: p.liquidity_usd)
        
        # Simple signal logic
        signal = "NEUTRAL"
        reasons = []
        
        # Price momentum
        if pair.price_change_1h > 5:
            signal = "BULLISH"
            reasons.append(f"Up {pair.price_change_1h:.1f}% in 1h")
        elif pair.price_change_1h < -5:
            signal = "BEARISH"
            reasons.append(f"Down {pair.price_change_1h:.1f}% in 1h")
        
        # Buy/sell pressure
        if pair.buy_sell_ratio > 1.5:
            if signal == "NEUTRAL":
                signal = "BULLISH"
            reasons.append(f"Strong buying ({pair.buy_sell_ratio:.1f}x more buys)")
        elif pair.buy_sell_ratio < 0.67:
            if signal == "NEUTRAL":
                signal = "BEARISH"
            reasons.append(f"Strong selling ({1/pair.buy_sell_ratio:.1f}x more sells)")
        
        # Volume check
        if pair.volume_24h > pair.liquidity_usd * 2:
            reasons.append("High volume (>2x liquidity)")
        
        return {
            'symbol': pair.symbol,
            'chain': pair.chain,
            'dex': pair.dex,
            'price': pair.price_usd,
            'price_change_1h': pair.price_change_1h,
            'price_change_24h': pair.price_change_24h,
            'volume_24h': pair.volume_24h,
            'liquidity': pair.liquidity_usd,
            'buy_sell_ratio': pair.buy_sell_ratio,
            'signal': signal,
            'reasons': reasons,
            'url': pair.url
        }


if __name__ == '__main__':
    print("🔍 DexScreener Meme Coin Scanner")
    print("=" * 50)
    
    dex = DexScreener()
    
    # Test search
    print("\n📊 Searching for PEPE...")
    analysis = dex.analyze_token("PEPE")
    if analysis:
        print(f"  Symbol: {analysis['symbol']}")
        print(f"  Chain: {analysis['chain']}")
        print(f"  Price: ${analysis['price']:.8f}")
        print(f"  1h Change: {analysis['price_change_1h']:+.1f}%")
        print(f"  24h Change: {analysis['price_change_24h']:+.1f}%")
        print(f"  Volume: ${analysis['volume_24h']:,.0f}")
        print(f"  Liquidity: ${analysis['liquidity']:,.0f}")
        print(f"  Signal: {analysis['signal']}")
        if analysis['reasons']:
            print(f"  Reasons: {', '.join(analysis['reasons'])}")
    
    # Test trending
    print("\n🔥 Top Solana Meme Coins by Volume...")
    trending = dex.get_trending('solana')
    for i, pair in enumerate(trending[:5], 1):
        emoji = "🟢" if pair.is_bullish() else "🔴" if pair.price_change_1h < 0 else "⚪"
        print(f"  {i}. {pair.symbol} {emoji}")
        print(f"     ${pair.price_usd:.6f} | 1h: {pair.price_change_1h:+.1f}% | Vol: ${pair.volume_24h:,.0f}")
