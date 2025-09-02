#!/bin/bash

# PackSense AWS Deployment Script
echo "🚀 Starting PackSense AWS Deployment..."

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    echo "❌ EB CLI not found. Installing..."
    pip install awsebcli
fi

# Initialize EB application (only needed once)
if [ ! -f ".elasticbeanstalk/config.yml" ]; then
    echo "📝 Initializing Elastic Beanstalk application..."
    eb init --platform python-3.9 --region us-east-1 PackSense
fi

# Create environment (only needed once)
if [ ! -f ".elasticbeanstalk/config.yml" ] || ! grep -q "environment:" .elasticbeanstalk/config.yml; then
    echo "🏗️ Creating Elastic Beanstalk environment..."
    eb create PackSense-prod --instance-type t3.medium --platform-version "Python 3.9"
fi

# Deploy the application
echo "📦 Deploying application..."
eb deploy

# Get the URL
echo "🌐 Getting application URL..."
eb status

echo "✅ Deployment complete!"
echo "🎯 Demo mode available at: https://your-app-url.elasticbeanstalk.com/demo"
echo "🏠 Main page: https://your-app-url.elasticbeanstalk.com"
