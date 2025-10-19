import json
import boto3
import hashlib
from datetime import datetime, timedelta
import os

class CacheManager:
    """
    High-performance caching system for Lambda functions
    Uses DynamoDB for persistent caching with TTL
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = os.getenv('CACHE_TABLE_NAME', 'position-details-cache')
        self.table = self.dynamodb.Table(self.table_name)
        
    def _generate_cache_key(self, data_type, *args):
        """Generate a consistent cache key from arguments"""
        key_string = f"{data_type}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, data_type, *args, ttl_hours=1):
        """Get cached data if it exists and is not expired"""
        try:
            cache_key = self._generate_cache_key(data_type, *args)
            response = self.table.get_item(Key={'cache_key': cache_key})
            
            if 'Item' in response:
                item = response['Item']
                # Check if cache is still valid
                if datetime.fromisoformat(item['expires_at']) > datetime.now():
                    return json.loads(item['data'])
                else:
                    # Cache expired, delete it
                    self.table.delete_item(Key={'cache_key': cache_key})
            
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    def set(self, data_type, data, *args, ttl_hours=1):
        """Set cached data with TTL"""
        try:
            cache_key = self._generate_cache_key(data_type, *args)
            expires_at = datetime.now() + timedelta(hours=ttl_hours)
            
            self.table.put_item(Item={
                'cache_key': cache_key,
                'data': json.dumps(data),
                'expires_at': expires_at.isoformat(),
                'created_at': datetime.now().isoformat(),
                'data_type': data_type
            })
        except Exception as e:
            print(f"Cache set error: {e}")
    
    def invalidate(self, data_type, *args):
        """Invalidate specific cache entries"""
        try:
            cache_key = self._generate_cache_key(data_type, *args)
            self.table.delete_item(Key={'cache_key': cache_key})
        except Exception as e:
            print(f"Cache invalidate error: {e}")

# Global cache instance
cache = CacheManager()
