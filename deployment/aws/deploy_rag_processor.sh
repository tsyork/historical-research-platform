#!/bin/bash

# Combined Steps 1-4: Complete AWS Instance Setup
# Launches instance, injects environment, installs dependencies, deploys files

set -e

echo "🚀 Combined AWS Instance Setup (Steps 1-4)"
echo "==========================================="
echo "This will:"
echo "  1. Launch c5.xlarge spot fleet instance"
echo "  2. Inject environment variables"
echo "  3. Install dependencies with latest versions"
echo "  4. Deploy processing files"
echo ""

# Check required files exist locally
echo "📋 Checking required files..."
required_files=(
    "deployment/aws/config/spot-fleet-config.json"
    "deployment/aws/config/whisper-transcription-key.pem"
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
echo "✅ All required files found"

# STEP 1: Launch Fleet
echo ""
echo "🔧 Step 1: Launching Spot Fleet"
echo "==============================="

cd deployment/aws/config
FLEET_ID=$(aws ec2 request-spot-fleet --spot-fleet-request-config file://spot-fleet-config.json --query 'SpotFleetRequestId' --output text)
cd ../../..

if [ -z "$FLEET_ID" ] || [ "$FLEET_ID" = "None" ]; then
    echo "❌ Failed to launch spot fleet"
    exit 1
fi

echo "✅ Fleet launched: $FLEET_ID"

# Wait for fulfillment
echo "⏳ Waiting for instance fulfillment..."
max_attempts=20
attempt=0

while [ $attempt -lt $max_attempts ]; do
    STATUS=$(aws ec2 describe-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --query 'SpotFleetRequestConfigs[0].ActivityStatus' --output text)
    echo "   Attempt $((attempt+1))/$max_attempts - Status: $STATUS"

    case $STATUS in
        "fulfilled")
            echo "✅ Fleet fulfilled successfully!"
            break
            ;;
        "error"|"cancelled_terminating"|"cancelled_running")
            echo "❌ Fleet failed with status: $STATUS"
            aws ec2 describe-spot-fleet-request-history --spot-fleet-request-id $FLEET_ID --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) 2>/dev/null || echo "Could not get fleet history"
            exit 1
            ;;
        *)
            sleep 30
            attempt=$((attempt+1))
            ;;
    esac
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Timeout waiting for fleet fulfillment"
    exit 1
fi

# Get instance details
echo "📡 Getting instance details..."
INSTANCE_ID=$(aws ec2 describe-spot-fleet-instances --spot-fleet-request-id $FLEET_ID --query 'ActiveInstances[0].InstanceId' --output text)
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
    echo "❌ Could not get instance ID"
    exit 1
fi

if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" = "None" ]; then
    echo "❌ Could not get public IP"
    exit 1
fi

echo "✅ Instance ID: $INSTANCE_ID"
echo "✅ Public IP: $PUBLIC_IP"

# Wait for SSH
echo "🔌 Waiting for SSH connectivity..."
max_ssh_attempts=15
ssh_attempt=0

while [ $ssh_attempt -lt $max_ssh_attempts ]; do
    echo "   SSH attempt $((ssh_attempt+1))/$max_ssh_attempts..."

    if ssh -i deployment/aws/config/whisper-transcription-key.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "echo 'SSH connection successful'" 2>/dev/null; then
        echo "✅ SSH connectivity confirmed!"
        break
    fi

    sleep 20
    ssh_attempt=$((ssh_attempt+1))
done

if [ $ssh_attempt -eq $max_ssh_attempts ]; then
    echo "❌ SSH connectivity failed"
    exit 1
fi

# STEP 2: Environment Variable Injection
echo ""
echo "🔧 Step 2: Environment Variable Injection"
echo "========================================="

echo "📝 Creating environment file with Python..."
python3 << 'PYTHON_SCRIPT'
import os

env_vars = {}
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

env_content = """#!/bin/bash
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

with open('temp_env_setup.sh', 'w') as f:
    f.write(env_content)

print("✅ Environment file created")
PYTHON_SCRIPT

scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no temp_env_setup.sh ubuntu@$PUBLIC_IP:~/env_setup.sh
rm temp_env_setup.sh

# Test environment variables
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'ENV_TEST'
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
ENV_TEST

echo "✅ Environment variables injected"

# STEP 3: Dependencies Installation
echo ""
echo "🔧 Step 3: Dependencies Installation"
echo "===================================="

ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'INSTALL_DEPS'
set -e

echo "🐍 Setting up Python environment..."
sudo apt update -y
sudo apt install -y python3.12-venv python3.12-dev curl

echo "📥 Installing pip for Python 3.12..."
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

echo "🔧 Creating virtual environment..."
python3.12 -m venv transcript_env

echo "⚡ Installing packages..."
source transcript_env/bin/activate

pip install --upgrade pip setuptools wheel
pip install --upgrade qdrant-client
pip install --upgrade openai
pip install google-cloud-storage==2.10.0
pip install google-api-python-client==2.108.0
pip install google-auth==2.23.4
pip install --only-binary=all tiktoken==0.7.0
pip install python-dotenv==1.0.0

echo "🧪 Testing package imports..."
python << 'PYTHON_TEST'
try:
    import qdrant_client
    print("✅ qdrant_client imported successfully")

    import openai
    print("✅ openai imported successfully")

    import google.cloud.storage
    print("✅ google.cloud.storage imported successfully")

    import tiktoken
    print("✅ tiktoken imported successfully")

    from dotenv import load_dotenv
    print("✅ python-dotenv imported successfully")

    print("🎉 All packages imported successfully!")

except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)
PYTHON_TEST

echo "💾 Creating activation script..."
cat > ~/activate_transcript_env.sh << 'ACTIVATE_SCRIPT'
#!/bin/bash
source ~/env_setup.sh
source ~/transcript_env/bin/activate
echo "🟢 Environment activated"
ACTIVATE_SCRIPT

chmod +x ~/activate_transcript_env.sh
echo "✅ Dependencies installed"
INSTALL_DEPS

echo "✅ Dependencies installation complete"

# STEP 4: File Deployment
echo ""
echo "🔧 Step 4: File Deployment"
echo "=========================="

echo "📤 Uploading files..."
scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no \
    data_processing/aws_transcript_processor.py ubuntu@$PUBLIC_IP:~/aws_transcript_processor.py

scp -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no \
    deployment/aws/config/credentials.json ubuntu@$PUBLIC_IP:~/credentials.json

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
VERIFY_FILES

# Test complete environment
echo "🧪 Testing complete environment setup..."
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'FINAL_TEST'
source ~/activate_transcript_env.sh

echo "Testing complete environment:"
echo "Python version: $(python --version)"
echo "QDRANT_CLOUD_URL: ${QDRANT_CLOUD_URL:0:30}..."
echo "Virtual environment: $VIRTUAL_ENV"

python << 'ENV_TEST'
import os
import qdrant_client
import openai
from dotenv import load_dotenv

load_dotenv()

print("✅ All packages imported successfully")
print(f"✅ QDRANT_CLOUD_URL available: {bool(os.getenv('QDRANT_CLOUD_URL'))}")
print(f"✅ OPENAI_API_KEY available: {bool(os.getenv('OPENAI_API_KEY'))}")
print("🎉 Complete environment test successful!")
ENV_TEST
FINAL_TEST

echo ""
echo "🎉 COMBINED SETUP COMPLETE!"
echo "=========================="
echo "✅ Fleet launched and instance ready"
echo "✅ Environment variables injected"
echo "✅ Dependencies installed with latest versions"
echo "✅ Files deployed and verified"
echo "✅ Complete environment tested"
echo ""
echo "Instance Details:"
echo "Fleet ID: $FLEET_ID"
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""
echo "Ready to run processing:"
echo "ssh -i deployment/aws/config/whisper-transcription-key.pem ubuntu@$PUBLIC_IP"
echo "source ~/activate_transcript_env.sh"
echo "python aws_transcript_processor.py"
echo ""
echo "To terminate:"
echo "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "💰 Estimated setup cost: ~$0.25-0.50"