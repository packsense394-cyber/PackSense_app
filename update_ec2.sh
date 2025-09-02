#!/bin/bash

# PackSense EC2 Update Script
echo "🔄 Updating PackSense on EC2..."

# Navigate to your PackSense directory (adjust path as needed)
cd /home/ec2-user/PackSense || cd /home/ubuntu/PackSense || cd ~/PackSense

# Stop the current application
echo "⏹️ Stopping current application..."
pkill -f "python.*app.py" || pkill -f "gunicorn" || echo "No running processes found"

# Backup current version (optional)
echo "💾 Creating backup..."
cp -r . ../PackSense_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "Backup skipped"

# Pull latest changes from git
echo "📥 Pulling latest changes..."
git fetch origin
git reset --hard origin/main

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Download NLTK data
echo "📚 Downloading NLTK data..."
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4'); nltk.download('vader_lexicon')"

# Set permissions
echo "🔐 Setting permissions..."
chmod +x *.sh 2>/dev/null || echo "No shell scripts to make executable"

# Start the application
echo "🚀 Starting updated application..."
nohup python app.py > app.log 2>&1 &

# Wait a moment and check if it's running
sleep 3
if pgrep -f "python.*app.py" > /dev/null; then
    echo "✅ PackSense updated and running successfully!"
    echo "🌐 Application should be available at: http://your-ec2-ip:5000"
    echo "🎯 Demo mode available at: http://your-ec2-ip:5000/demo"
else
    echo "❌ Application failed to start. Check app.log for errors."
    echo "📋 Last 20 lines of app.log:"
    tail -20 app.log
fi

echo "📊 Process status:"
ps aux | grep -E "(python|app\.py)" | grep -v grep
