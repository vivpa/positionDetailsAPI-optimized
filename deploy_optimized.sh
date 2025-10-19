#!/bin/bash

# Optimized Position Details API Deployment Script
# This script deploys the performance-optimized version

set -e

echo "🚀 Deploying Optimized Position Details API"
echo "============================================="

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

echo "✅ AWS CLI configured"

# Backup current files
echo "📦 Creating backup of current files..."
mkdir -p backup_$(date +%Y%m%d_%H%M%S)
cp -r hello_world backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
cp template.yaml backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true

# Deploy optimized version
echo "🔧 Deploying optimized version..."

# Update Dockerfile to use optimized app
echo "FROM public.ecr.aws/lambda/python:3.9
COPY functions ./functions
COPY app_optimized.py ./app.py
COPY requirements_optimized.txt ./requirements.txt

RUN python3.9 -m pip install -r requirements.txt -t .

CMD [\"app.lambda_handler\"]" > hello_world/Dockerfile

# Update template.yaml
cp template_optimized.yaml template.yaml

echo "📋 Updated configuration:"
echo "   - Memory: 3008MB (optimized)"
echo "   - Timeout: 60s (reduced from 600s)"
echo "   - Added DynamoDB caching"
echo "   - Added performance monitoring"

# Build and deploy
echo "🏗️  Building and deploying..."
sam build --use-container

echo "🚀 Deploying to AWS..."
sam deploy --guided --parameter-overrides \
    SentryDSN="" \
    SentryTracesSampleRate=0.1 \
    SentryProfileSampleRate=0.1

echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Performance Optimizations Applied:"
echo "   ✅ Concurrent API calls (aiohttp)"
echo "   ✅ DynamoDB caching with TTL"
echo "   ✅ Reduced data extraction period (2 years vs 5)"
echo "   ✅ Optimized pandas operations"
echo "   ✅ Batch processing"
echo "   ✅ Performance monitoring"
echo ""
echo "🎯 Expected Performance:"
echo "   - Target: < 15 seconds"
echo "   - Expected improvement: 60-80% faster"
echo ""
echo "📈 Next Steps:"
echo "   1. Test the deployed function"
echo "   2. Monitor CloudWatch logs"
echo "   3. Run performance tests"
echo "   4. Monitor DynamoDB cache usage"
echo ""
echo "🔍 To test performance:"
echo "   python performance_test.py"
