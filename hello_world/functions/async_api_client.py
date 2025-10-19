import asyncio
import aiohttp
import json
from typing import List, Dict, Any
import time

class AsyncAPIClient:
    """
    High-performance async API client for concurrent requests
    """
    
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_quotes_batch(self, tickers: List[str]) -> Dict[str, Any]:
        """Fetch quotes for multiple tickers concurrently"""
        if not tickers:
            return {}
            
        tickers_str = ','.join(tickers)
        url = f"https://api-v2.intrinio.com/stock_exchanges/USCOMP/quote?tickers={tickers_str}&api_key={self.api_key}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {quote['security']['ticker']: quote for quote in data.get('quotes', [])}
                else:
                    print(f"API error: {response.status}")
                    return {}
        except Exception as e:
            print(f"Error fetching quotes: {e}")
            return {}
    
    async def fetch_option_prices_batch(self, option_tickers: List[str]) -> Dict[str, Any]:
        """Fetch option prices for multiple contracts concurrently"""
        if not option_tickers:
            return {}
            
        url = "https://api-v2.intrinio.com/options/prices/realtime/batch"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f'Bearer {self.api_key}'
        }
        params = {
            "source": "delayed",
            "show_stats": "true",
            "stock_price_source": "bats_delayed",
            "model": "black_scholes",
            "show_extended_price": "true",
            "api_key": self.api_key
        }
        body = {"contracts": option_tickers}
        
        try:
            async with self.session.post(url, headers=headers, params=params, json=body) as response:
                if response.status == 200:
                    data = await response.json()
                    return {contract['option']['code']: contract for contract in data.get('contracts', [])}
                else:
                    print(f"Option API error: {response.status}")
                    return {}
        except Exception as e:
            print(f"Error fetching option prices: {e}")
            return {}

async def fetch_all_data_concurrent(api_key: str, tickers: List[str], option_tickers: List[str]) -> tuple:
    """
    Fetch all external data concurrently to minimize latency
    """
    async with AsyncAPIClient(api_key) as client:
        # Run both API calls concurrently
        quotes_task = client.fetch_quotes_batch(tickers)
        options_task = client.fetch_option_prices_batch(option_tickers)
        
        quotes_data, options_data = await asyncio.gather(quotes_task, options_task)
        
        return quotes_data, options_data

def fetch_all_data_sync(api_key: str, tickers: List[str], option_tickers: List[str]) -> tuple:
    """
    Synchronous wrapper for the async function
    """
    return asyncio.run(fetch_all_data_concurrent(api_key, tickers, option_tickers))
