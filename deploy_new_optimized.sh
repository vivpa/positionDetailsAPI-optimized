#!/bin/bash

# Deploy Optimized Position Details API to New Lambda Function
# This script deploys the Redis-cached optimized version as a new function

set -e

echo "🚀 Deploying Optimized Position Details API to New Lambda Function"
echo "=================================================================="

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

echo "✅ AWS CLI configured"

# 1. Update requirements.txt to include Redis
echo "📦 Setting up Redis dependencies..."
cp hello_world/requirements_redis.txt hello_world/requirements.txt

# 2. Update Dockerfile to use Redis-enabled app
echo "🐳 Updating Dockerfile for Redis..."
cat > hello_world/Dockerfile << 'EOF'
FROM public.ecr.aws/lambda/python:3.9
COPY functions ./functions
COPY app_redis.py ./app.py
COPY requirements.txt ./

RUN python3.9 -m pip install -r requirements.txt -t .

CMD ["app.lambda_handler"]
EOF

# 3. Use the Redis template
echo "📋 Using Redis-enabled template..."
cp template_redis.yaml template.yaml

# 4. Build the application
echo "🏗️ Building optimized application..."
sam build --use-container

echo ""
echo "📋 Deployment Configuration:"
echo "   ✅ Function Name: PositionDetailsOptimizedFunction"
echo "   ✅ API Path: /position-details (POST)"
echo "   ✅ Memory: 3008 MB (optimized)"
echo "   ✅ Timeout: 60 seconds"
echo "   ✅ Redis Cluster: t3.micro ($12/month)"
echo "   ✅ VPC Configuration: Secure Redis access"
echo ""
echo "🎯 Expected Performance:"
echo "   - Execution time: 5-9 seconds (vs 29s original)"
echo "   - Cache hit rate: 80-90%"
echo "   - Memory usage: 3GB (vs 10GB original)"
echo ""
echo "💰 Cost Analysis:"
echo "   - Redis cluster: $12/month"
echo "   - VPC resources: ~$5/month"
echo "   - Break-even: ~2400 requests/month"
echo ""
echo "🚀 Ready to deploy! Run: sam deploy --guided"
echo ""
echo "📈 After deployment, test with:"
echo "   python performance_test.py"
