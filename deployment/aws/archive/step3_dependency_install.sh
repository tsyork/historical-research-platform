#!/bin/bash

# Step 3: Dependency Installation
# Uses existing Python 3.12 from AMI, installs required packages

set -e

echo "🔧 Step 3: Dependency Installation"
echo "=================================="

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

# Install dependencies on the instance
echo "📦 Installing Python dependencies..."
ssh -i deployment/aws/config/whisper-transcription-key.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP << 'REMOTE_INSTALL'
set -e

echo "🐍 Checking Python 3.12 availability..."
python3.12 --version

echo "📋 Installing system dependencies..."
sudo apt update -y
sudo apt install -y python3.12-venv python3.12-dev curl

echo "📥 Installing pip for Python 3.12..."
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

echo "🔧 Creating virtual environment..."
python3.12 -m venv transcript_env

echo "⚡ Activating environment and installing packages..."
source transcript_env/bin/activate

echo "📦 Installing core packages..."
pip install --upgrade pip setuptools wheel

echo "📦 Installing RAG and vector database packages..."
pip install --upgrade qdrant-client
pip install --upgrade openai

echo "📦 Installing Google Cloud packages..."
pip install google-cloud-storage==2.10.0
pip install google-api-python-client==2.108.0
pip install google-auth==2.23.4

echo "📦 Installing processing packages..."
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
echo "🟢 Environment activated with transcript processing packages and environment variables"
ACTIVATE_SCRIPT

chmod +x ~/activate_transcript_env.sh

echo "✅ Dependencies installed successfully"
echo "✅ Virtual environment created: ~/transcript_env/"
echo "✅ Activation script created: ~/activate_transcript_env.sh"
REMOTE_INSTALL

# Test that everything works together
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

print(f"✅ Qdrant client imported successfully")
print(f"✅ QDRANT_CLOUD_URL available: {bool(os.getenv('QDRANT_CLOUD_URL'))}")
print(f"✅ OPENAI_API_KEY available: {bool(os.getenv('OPENAI_API_KEY'))}")
print("🎉 Complete environment test successful!")
ENV_TEST
FINAL_TEST

echo ""
echo "🎉 Step 3 SUCCESSFUL - Dependencies installed!"
echo "=============================================="
echo "✅ Python 3.12 virtual environment created"
echo "✅ All required packages installed with specific versions"
echo "✅ Environment variables integrated"
echo "✅ Activation script created for easy setup"
echo ""
echo "Fleet ID: $FLEET_ID"
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""
echo "To use environment on instance:"
echo "ssh -i deployment/aws/config/whisper-transcription-key.pem ubuntu@$PUBLIC_IP"
echo "source ~/activate_transcript_env.sh"
echo ""
echo "To terminate:"
echo "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "🔄 Ready for Step 4: File deployment"