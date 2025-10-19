import json
import pickle
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import redis
import os

class FinancialDataCache:
    """
    High-performance Redis cache for financial position details API
    Optimized for market data patterns and TTL management
    """
    
    def __init__(self):
        # Get Redis connection from environment
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD', None)
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=False,  # Keep binary for pickle
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            self.redis_client.ping()
            print("✅ Redis connection established")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, data_type: str, *args) -> str:
        """Generate consistent cache keys"""
        # Create a hash of all arguments
        key_string = f"{data_type}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for Redis storage"""
        return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data from Redis"""
        return pickle.loads(data)
    
    def get_historical_data(self, tickers: List[str], start_date: str, end_date: str) -> Optional[Dict]:
        """Get cached historical price data"""
        if not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key('historical', tuple(sorted(tickers)), start_date, end_date)
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = self._deserialize_data(cached_data)
                print(f"✅ Cache HIT: Historical data for {len(tickers)} tickers")
                return data
            else:
                print(f"❌ Cache MISS: Historical data for {len(tickers)} tickers")
                return None
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return None
    
    def set_historical_data(self, tickers: List[str], start_date: str, end_date: str, 
                           data: Dict, ttl_hours: int = 4) -> bool:
        """Cache historical price data"""
        if not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key('historical', tuple(sorted(tickers)), start_date, end_date)
        
        try:
            serialized_data = self._serialize_data(data)
            ttl_seconds = ttl_hours * 3600
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            print(f"✅ Cached: Historical data for {len(tickers)} tickers (TTL: {ttl_hours}h)")
            return True
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return False
    
    def get_api_quotes(self, tickers: List[str]) -> Optional[Dict]:
        """Get cached API quotes data"""
        if not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key('quotes', tuple(sorted(tickers)))
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = self._deserialize_data(cached_data)
                print(f"✅ Cache HIT: Quotes data for {len(tickers)} tickers")
                return data
            else:
                print(f"❌ Cache MISS: Quotes data for {len(tickers)} tickers")
                return None
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return None
    
    def set_api_quotes(self, tickers: List[str], data: Dict, ttl_minutes: int = 15) -> bool:
        """Cache API quotes data"""
        if not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key('quotes', tuple(sorted(tickers)))
        
        try:
            serialized_data = self._serialize_data(data)
            ttl_seconds = ttl_minutes * 60
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            print(f"✅ Cached: Quotes data for {len(tickers)} tickers (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return False
    
    def get_options_data(self, option_tickers: List[str]) -> Optional[Dict]:
        """Get cached options data"""
        if not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key('options', tuple(sorted(option_tickers)))
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = self._deserialize_data(cached_data)
                print(f"✅ Cache HIT: Options data for {len(option_tickers)} contracts")
                return data
            else:
                print(f"❌ Cache MISS: Options data for {len(option_tickers)} contracts")
                return None
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return None
    
    def set_options_data(self, option_tickers: List[str], data: Dict, ttl_minutes: int = 15) -> bool:
        """Cache options data"""
        if not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key('options', tuple(sorted(option_tickers)))
        
        try:
            serialized_data = self._serialize_data(data)
            ttl_seconds = ttl_minutes * 60
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            print(f"✅ Cached: Options data for {len(option_tickers)} contracts (TTL: {ttl_minutes}m)")
            return True
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return False
    
    def get_earnings_dividends(self, data_type: str) -> Optional[Dict]:
        """Get cached earnings or dividends data"""
        if not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key(data_type, 'all')
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = self._deserialize_data(cached_data)
                print(f"✅ Cache HIT: {data_type} data")
                return data
            else:
                print(f"❌ Cache MISS: {data_type} data")
                return None
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return None
    
    def set_earnings_dividends(self, data_type: str, data: Dict, ttl_hours: int = 24) -> bool:
        """Cache earnings or dividends data"""
        if not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key(data_type, 'all')
        
        try:
            serialized_data = self._serialize_data(data)
            ttl_seconds = ttl_hours * 3600
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            print(f"✅ Cached: {data_type} data (TTL: {ttl_hours}h)")
            return True
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return False
    
    def get_calculated_metrics(self, ticker: str, metric_type: str) -> Optional[Dict]:
        """Get cached calculated metrics (RSI, volatility, etc.)"""
        if not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key('metrics', ticker, metric_type)
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = self._deserialize_data(cached_data)
                print(f"✅ Cache HIT: {metric_type} for {ticker}")
                return data
            else:
                print(f"❌ Cache MISS: {metric_type} for {ticker}")
                return None
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return None
    
    def set_calculated_metrics(self, ticker: str, metric_type: str, data: Dict, ttl_hours: int = 2) -> bool:
        """Cache calculated metrics"""
        if not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key('metrics', ticker, metric_type)
        
        try:
            serialized_data = self._serialize_data(data)
            ttl_seconds = ttl_hours * 3600
            self.redis_client.setex(cache_key, ttl_seconds, serialized_data)
            print(f"✅ Cached: {metric_type} for {ticker} (TTL: {ttl_hours}h)")
            return True
        except Exception as e:
            print(f"⚠️ Cache error: {e}")
            return False
    
    def invalidate_market_data(self):
        """Invalidate all market data at market close"""
        if not self.redis_client:
            return False
        
        try:
            # Get all keys with market data patterns
            patterns = ['historical:*', 'quotes:*', 'options:*', 'metrics:*']
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    print(f"✅ Invalidated {len(keys)} keys matching {pattern}")
            return True
        except Exception as e:
            print(f"⚠️ Cache invalidation error: {e}")
            return False
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if not self.redis_client:
            return {"error": "Redis not connected"}
        
        try:
            info = self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0

# Global cache instance
financial_cache = FinancialDataCache()
