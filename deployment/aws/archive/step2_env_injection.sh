#!/bin/bash

# Step 2: Environment Variable Injection
# This script safely injects environment variables using Python instead of sed

set -e

echo "🔧 Step 2: Environment Variable Injection"
echo "========================================="

# Use your existing fleet details
FLEET_ID="sfr-5ef59571-28bf-4301-8802-7660f401322e"
INSTANCE_ID="i-0739f7eed9539a325"
PUBLIC_IP="35.89.19.130"

echo "📡 Using instance: $INSTANCE_ID ($PUBLIC_IP)"

# Test SSH connectivity first
echo "🔌 Testing SSH connectivity..."
if ! ssh -i deployment/aws/config/whisper-transcription-key.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "echo 'SSH test successful'" 2>/dev/null; then
    echo "❌ SSH connection failed. Instance may still be starting."
    exit 1
fi
echo "✅ SSH connectivity confirmed"

# Create environment file using Python (avoids sed issues with special characters)
echo "📝 Creating environment file with Python..."
python3 << 'PYTHON_SCRIPT'
import os

# Read environment variables from .env file
env_vars = {}
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

# Create the environment script content
env_content = """#!/bin/bash
# Environment variables for transcript processing
export QDRANT_CLOUD_URL="{qdrant_url}"
export QDRANT_CLOUD_API_KEY="{qdrant_key}"
export OPENAI_API_KEY="{openai_key}"
export ANTHROPIC_API_KEY="{anthropic_key}"
export GCS_PROJECT_ID="{gcs_project}"
export GCS_BUCKET_NAME="{gcs_bucket}"
export QDRANT_COLLECTION_NAME="{collection_name}"
""".format(
    qdrant_url=env_vars.get('QDRANT_CLOUD_URL', ''),
    qdrant_key=env_vars.get('QDRANT_CLOUD_API_KEY', ''),
    openai_key=env_vars.get('OPENAI_API_KEY', ''),
    anthropic_key=env_vars.get('ANTHROPIC_API_KEY', ''),
    gcs_project=env_vars.get('GCS_PROJECT_ID', ''),
    gcs_bucket=env_vars.get('GCS_BUCKET_NAME', ''),
    collection_name=env_vars.get('QDRANT_COLLECTION_NAME', '')
)

# Write to temporary file
with open('temp_env_setup.sh', 'w') as f:
    f.write(env_content)

print("✅ Environment file created successfully")
PYTHON_SCRIPT

# Check if environment file was created
if [ ! -f "temp_env_setup.sh" ]; then
    echo "❌ Failed to create environment file"
    exit 1
fi

echo "📤 Uploading environment file to instance..."
scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no temp_env_setup.sh ubuntu@$PUBLIC_IP:~/env_setup.sh

# Test that environment variables are accessible on the instance
echo "🧪 Testing environment variable injection..."
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'REMOTE_TEST'
chmod +x ~/env_setup.sh
source ~/env_setup.sh

echo "Testing environment variables:"
echo "QDRANT_CLOUD_URL: ${QDRANT_CLOUD_URL:0:30}..."
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:0:20}..."
echo "GCS_PROJECT_ID: $GCS_PROJECT_ID"

if [ -z "$QDRANT_CLOUD_URL" ] || [ -z "$OPENAI_API_KEY" ] || [ -z "$GCS_PROJECT_ID" ]; then
    echo "❌ Environment variables not properly set"
    exit 1
else
    echo "✅ Environment variables successfully injected"
fi
REMOTE_TEST

# Cleanup temporary file
rm temp_env_setup.sh

echo ""
echo "🎉 Step 2 SUCCESSFUL - Environment variables injected!"
echo "====================================================="
echo "✅ Environment file uploaded to instance"
echo "✅ Variables are accessible via: source ~/env_setup.sh"
echo "✅ No sed commands used (avoided special character issues)"
echo ""
echo "Fleet ID: $FLEET_ID"
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""
echo "To terminate:"
echo "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "🔄 Ready for Step 3: Dependency installation"