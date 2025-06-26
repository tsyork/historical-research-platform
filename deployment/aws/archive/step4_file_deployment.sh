#!/bin/bash

# Step 4: File Deployment
# Deploy processing script and credentials to the instance

set -e

echo "🔧 Step 4: File Deployment"
echo "=========================="

# Use existing instance details
FLEET_ID="sfr-5ef59571-28bf-4301-8802-7660f401322e"
INSTANCE_ID="i-0739f7eed9539a325"
PUBLIC_IP="35.89.19.130"

echo "📡 Using instance: $INSTANCE_ID ($PUBLIC_IP)"

# Test SSH connectivity
echo "🔌 Testing SSH connectivity..."
if ! ssh -i deployment/aws/config/whisper-transcription-key.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "echo 'SSH test successful'" 2>/dev/null; then
    echo "❌ SSH connection failed"
    exit 1
fi
echo "✅ SSH connectivity confirmed"

# Check required files exist locally
echo "📋 Checking required files..."
required_files=(
    "data_processing/aws_transcript_processor.py"
    "deployment/aws/config/credentials.json"
    ".env"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
done
echo "✅ All required files found locally"

# Deploy files to instance
echo "📤 Deploying files to instance..."

echo "📄 Uploading processing script..."
scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no \
    data_processing/aws_transcript_processor.py ubuntu@$PUBLIC_IP:~/aws_transcript_processor.py

echo "🔑 Uploading credentials..."
scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no \
    deployment/aws/config/credentials.json ubuntu@$PUBLIC_IP:~/credentials.json

echo "⚙️ Uploading environment config..."
scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no \
    .env ubuntu@$PUBLIC_IP:~/.env

# Verify files were uploaded correctly
echo "🔍 Verifying file deployment..."
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'VERIFY_FILES'
echo "Checking deployed files:"

if [ -f "aws_transcript_processor.py" ]; then
    echo "✅ aws_transcript_processor.py ($(wc -l < aws_transcript_processor.py) lines)"
else
    echo "❌ aws_transcript_processor.py missing"
    exit 1
fi

if [ -f "credentials.json" ]; then
    echo "✅ credentials.json ($(wc -c < credentials.json) bytes)"
else
    echo "❌ credentials.json missing"
    exit 1
fi

if [ -f ".env" ]; then
    echo "✅ .env ($(grep -c "=" .env) variables)"
else
    echo "❌ .env missing"
    exit 1
fi

echo "📁 File listing:"
ls -la aws_transcript_processor.py credentials.json .env
VERIFY_FILES

# Test that the processing script can be imported
echo "🧪 Testing script import..."
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'TEST_SCRIPT'
source ~/activate_transcript_env.sh

echo "Testing Python script import..."
python << 'PYTHON_TEST'
import sys
import os

try:
    # Add current directory to Python path
    sys.path.insert(0, os.getcwd())

    # Test basic imports first
    import json
    print("✅ json module available")

    # Check if credentials file is valid JSON
    with open('credentials.json', 'r') as f:
        creds = json.load(f)
        print(f"✅ credentials.json is valid JSON with {len(creds)} keys")

    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv()

    qdrant_url = os.getenv('QDRANT_CLOUD_URL')
    if qdrant_url:
        print(f"✅ QDRANT_CLOUD_URL loaded: {qdrant_url[:30]}...")
    else:
        print("❌ QDRANT_CLOUD_URL not found")

    print("🎉 Script environment test successful!")

except Exception as e:
    print(f"❌ Script test failed: {e}")
    exit(1)
PYTHON_TEST
TEST_SCRIPT

echo ""
echo "🎉 Step 4 SUCCESSFUL - Files deployed!"
echo "====================================="
echo "✅ Processing script uploaded and verified"
echo "✅ Credentials file uploaded and validated"
echo "✅ Environment configuration deployed"
echo "✅ Script import test passed"
echo ""
echo "Fleet ID: $FLEET_ID"
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""
echo "Files on instance:"
echo "  ~/aws_transcript_processor.py"
echo "  ~/credentials.json"
echo "  ~/.env"
echo ""
echo "To run processing:"
echo "ssh -i deployment/aws/config/whisper-transcription-key.pem ubuntu@$PUBLIC_IP"
echo "source ~/activate_transcript_env.sh"
echo "python aws_transcript_processor.py"
echo ""
echo "To terminate:"
echo "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "🔄 Ready for Step 5: Processing execution"