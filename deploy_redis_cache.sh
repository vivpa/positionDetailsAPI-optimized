#!/bin/bash

# Redis Caching Implementation for Position Details API
# This script deploys Redis caching to achieve <15 second performance

set -e

echo "🚀 Deploying Redis Caching for Position Details API"
echo "=================================================="

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

echo "✅ AWS CLI configured"

# 1. Update requirements.txt to include Redis
echo "📦 Adding Redis dependencies..."
cat > hello_world/requirements_redis.txt << 'EOF'
boto3==1.25.3
botocore==1.28.3
jmespath==1.0.1
numpy==1.23.4
pandas==1.5.1
python-dateutil==2.8.2
pytz==2022.5
s3transfer==0.6.0
six==1.16.0
urllib3==1.26.12
asn1crypto==1.5.1
certifi==2022.9.24
cffi==1.15.1
charset-normalizer==2.0.12
cryptography==36.0.2
idna==3.4
intrinio-sdk==6.34.0
oscrypto==1.3.0
py4j==0.10.9.5
pandas_market_calendars==4.4.0
pandas-datareader==0.10.0
pyarrow==6.0.1
pycparser==2.21
pycryptodomex==3.15.0
PyJWT==2.6.0
pyOpenSSL==22.0.0
requests==2.28.1
snowflake-connector-python==2.7.9
debugpy>=1.0,<2
# Redis caching dependencies
redis==4.6.0
aiohttp==3.8.5
asyncio-throttle==1.0.2
sentry-sdk==1.32.0
EOF

# 2. Update Dockerfile to use Redis-enabled app
echo "🐳 Updating Dockerfile for Redis..."
cat > hello_world/Dockerfile << 'EOF'
FROM public.ecr.aws/lambda/python:3.9
COPY functions ./functions
COPY app_redis.py ./app.py
COPY requirements_redis.txt ./requirements.txt

RUN python3.9 -m pip install -r requirements.txt -t .

CMD ["app.lambda_handler"]
EOF

# 3. Create Redis-enabled app.py
echo "📝 Creating Redis-enabled app.py..."
cat > hello_world/app_redis.py << 'EOF'
import json
from datetime import datetime
import sys
import os
import re
import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
import time

# Import Redis-cached functions
from functions.calcPositionsDetails_redis import calcPositionsDetails 
from functions.validateRequestBody import validateRequestBody 
from functions.financial_cache import financial_cache

# Initialize Sentry with environment variable
sentry_dsn = os.getenv('SENTRY_DSN')
if sentry_dsn:
    traces_sample_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))
    profile_sample_rate = float(os.getenv('SENTRY_PROFILE_SAMPLE_RATE', '0.1'))
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=traces_sample_rate,
        profile_session_sample_rate=profile_sample_rate,
        profile_lifecycle="trace",
        integrations=[
            AwsLambdaIntegration(timeout_warning=True),
        ],
    )
    print(f"Sentry initialized with traces_sample_rate={traces_sample_rate}, profile_sample_rate={profile_sample_rate}")
else:
    print("Warning: SENTRY_DSN environment variable not set. Sentry monitoring disabled.") 

class RedisCachedCalculator:
    """Redis-cached calculator with performance monitoring"""
    
    @staticmethod
    def calcDetails(jsonPortfolioStatsInput: str) -> str:
        """Redis-cached calculation process with timing"""
        start_time = time.time()
        print(f"Starting Redis-cached calcDetails at {start_time}")
        
        try:
            jsonPortfolioStatsOutput = calcPositionsDetails(jsonPortfolioStatsInput)
            print(f"Redis-cached calcDetails completed in {time.time() - start_time:.2f}s")
            return jsonPortfolioStatsOutput
        except Exception as e:
            print(f"Error in Redis-cached calcDetails: {e}")
            raise
    
def mask_api_key_in_url(message):
    """Mask API keys in error messages"""
    if "api_key=" in message:
        return re.sub(r"(api_key=)[^&]+", r"\1****", message)
    return message

def lambda_handler(event, context): 
    """Redis-cached Lambda handler with performance monitoring"""
    print('Entered Redis-cached lambda handler') 
    
    # Start comprehensive timing
    total_start_time = time.time()
    
    try:
        # Parse event body
        parse_start = time.time()
        parsedBody = json.loads(event["body"]) 
        print(f"Event parsing completed in {time.time() - parse_start:.2f}s")

        print("parsedBody: ", parsedBody) 

        # Validate request body
        validation_start = time.time()
        valid, validMsg = validateRequestBody(parsedBody)
        if not valid:
            return {"statusCode": 400, "body": validMsg}
        print(f"Request validation completed in {time.time() - validation_start:.2f}s")

        # Perform Redis-cached calculations
        print("Starting Redis-cached function call")
        calc_start = time.time()
        jsonPositionDetails = RedisCachedCalculator.calcDetails(json.dumps(parsedBody))
        print(f"Redis-cached function call completed in {time.time() - calc_start:.2f}s")

        # Parse output
        output_start = time.time()
        dictPositionDetails = json.loads(jsonPositionDetails) 
        print(f"Output parsing completed in {time.time() - output_start:.2f}s")

        print("Output", dictPositionDetails)

        # Calculate total execution time
        total_time = time.time() - total_start_time
        print(f"Total Lambda execution time: {total_time:.2f}s")

        # Get cache statistics
        cache_stats = financial_cache.get_cache_stats()
        print(f"Cache stats: {cache_stats}")

        # Add performance metrics to response headers
        response_headers = {
            "Content-Type": "application/json",
            "X-Execution-Time": f"{total_time:.2f}s",
            "X-Performance-Optimized": "redis-cached",
            "X-Cache-Hit-Rate": f"{cache_stats.get('hit_rate', 0):.1f}%"
        }

        return {
            "statusCode": 200, 
            "body": json.dumps(dictPositionDetails),
            "headers": response_headers
        }

    except Exception as ex:
        ex_type, ex_value, ex_traceback = sys.exc_info()

        # Capture error with Sentry
        if sentry_dsn:
            print("Capturing error with Sentry")
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("service", "position details api")
                scope.set_tag("stage", "production")
                scope.set_tag("cache_enabled", "redis")
                scope.set_context("request", {
                    "request_id": context.aws_request_id if context else None,
                    "timestamp": datetime.now().isoformat(),
                    "execution_time": f"{time.time() - total_start_time:.2f}s"
                })
                sentry_sdk.capture_exception(ex)

        message = mask_api_key_in_url(str(ex_value))
        error_response = {
            "error": {
                "type": ex_type.__name__,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "request_id": context.aws_request_id if context else None,
                "execution_time": f"{time.time() - total_start_time:.2f}s",
                "details": {
                    "service": "position details api",
                    "stage": "production",
                    "cache_enabled": "redis"
                }
            }
        }

        return {
            "statusCode": 400,
            "body": json.dumps(error_response),
            "headers": {
                "Content-Type": "application/json",
                "X-Execution-Time": f"{time.time() - total_start_time:.2f}s"
            }
        }
EOF

# 4. Deploy the Redis-enabled version
echo "🚀 Deploying Redis-cached version..."
cp template_redis.yaml template.yaml

sam build --use-container

echo "📋 Redis Caching Implementation Summary:"
echo "   ✅ ElastiCache Redis cluster (t3.micro - $12/month)"
echo "   ✅ VPC configuration for secure access"
echo "   ✅ Multi-level caching strategy"
echo "   ✅ Performance monitoring and cache stats"
echo "   ✅ Graceful fallback if Redis fails"
echo ""
echo "🎯 Expected Performance Improvements:"
echo "   - Historical data: 15-20 seconds saved (cache hit)"
echo "   - API responses: 3-5 seconds saved (cache hit)"
echo "   - Earnings/dividends: 1-2 seconds saved (cache hit)"
echo "   - Total improvement: 80-85% (from 29s to 5-9s)"
echo ""
echo "💰 Cost Analysis:"
echo "   - Redis cluster: $12/month"
echo "   - Break-even: ~2400 requests/month"
echo "   - Expected cache hit rate: 80-90%"
echo ""
echo "📈 Next Steps:"
echo "   1. Deploy: sam deploy --guided"
echo "   2. Test the function with various portfolios"
echo "   3. Monitor cache hit rates in CloudWatch"
echo "   4. Optimize TTL values based on usage patterns"
echo ""
echo "🔍 Cache Key Strategy:"
echo "   - Historical data: 4-6 hours TTL"
echo "   - API responses: 15-30 minutes TTL"
echo "   - Earnings/dividends: 24 hours TTL"
echo "   - Calculated metrics: 1-2 hours TTL"
