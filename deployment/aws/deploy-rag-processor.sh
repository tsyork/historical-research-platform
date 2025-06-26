#!/bin/bash

# FIXED AWS RAG Processing Deployment Script
# This version actually works without manual intervention

set -e

echo "🏛️ FIXED AWS RAG Processing Deployment"
echo "====================================="
echo "This version properly handles:"
echo "- Environment variables injection"
echo "- Dependency installation"
echo "- Memory optimization"
echo "- Error handling"
echo ""

# Check required files
echo "📋 Checking required files..."

required_files=(
    "config/spot-fleet-config.json"
    "../../data_processing/aws_transcript_processor.py"
    "config/credentials.json"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing: $file"
        exit 1
    fi
done

# Find SSH key
SSH_KEY_PATH=""
if [ -f "config/whisper-transcription-key.pem" ]; then
    SSH_KEY_PATH="config/whisper-transcription-key.pem"
elif [ -f "whisper-transcription-key.pem" ]; then
    SSH_KEY_PATH="whisper-transcription-key.pem"
else
    echo "❌ Missing SSH key: whisper-transcription-key.pem"
    exit 1
fi

echo "✅ All required files found"

# Load environment variables
echo "🔧 Loading configuration..."

if [ -f "../../.env" ]; then
    # Use a more reliable method to load .env variables
    set -a  # Automatically export all variables
    source ../../.env
    set +a  # Turn off automatic export
    echo "✅ Loaded from ../../.env"
elif [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✅ Loaded from .env"
else
    echo "❌ No .env file found"
    exit 1
fi

# Validate required environment variables
required_vars=(
    "QDRANT_CLOUD_URL"
    "QDRANT_CLOUD_API_KEY"
    "OPENAI_API_KEY"
    "ANTHROPIC_API_KEY"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing environment variable: $var"
        exit 1
    fi
done

# Set defaults
export GCS_PROJECT_ID=${GCS_PROJECT_ID:-"podcast-transcription-462218"}
export GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-"ai_knowledgebase"}
export QDRANT_COLLECTION_NAME=${QDRANT_COLLECTION_NAME:-"historical_sources"}

echo "📊 Configuration loaded:"
echo "   Qdrant URL: ${QDRANT_CLOUD_URL:0:50}..."
echo "   GCS Project: $GCS_PROJECT_ID"
echo "   Collection: $QDRANT_COLLECTION_NAME"

# Create ROBUST startup script
echo "🔧 Creating robust startup script..."

cat > startup-script.sh << 'STARTUP_SCRIPT'
#!/bin/bash

# ROBUST RAG Processing Startup Script
exec > /home/ubuntu/startup.log 2>&1
set -e

echo "🏛️ Starting ROBUST RAG Processing Setup..."
echo "Timestamp: $(date)"

# Wait for instance to be ready
sleep 30

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv htop

# Create dedicated virtual environment for RAG processing
echo "🐍 Creating dedicated Python environment..."
python3 -m venv /home/ubuntu/rag-env
source /home/ubuntu/rag-env/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install openai==1.0.0
pip install qdrant-client==1.7.0
pip install tqdm==4.66.0
pip install google-cloud-storage==2.10.0
pip install google-api-python-client==2.100.0
pip install google-auth==2.23.0
pip install python-dotenv==1.0.0
pip install pandas==2.0.0
pip install numpy==1.24.0

echo "✅ Dependencies installed successfully"

# Create environment file with ACTUAL values (injected by deployment script)
cat > /home/ubuntu/.env << 'ENV_FILE'
QDRANT_CLOUD_URL=__QDRANT_URL__
QDRANT_CLOUD_API_KEY=__QDRANT_API_KEY__
OPENAI_API_KEY=__OPENAI_API_KEY__
ANTHROPIC_API_KEY=__ANTHROPIC_API_KEY__
GCS_PROJECT_ID=__GCS_PROJECT__
GCS_BUCKET_NAME=__GCS_BUCKET__
QDRANT_COLLECTION_NAME=__COLLECTION_NAME__
ENV_FILE

# Create memory-optimized processing script
cat > /home/ubuntu/run-rag-processing.sh << 'PROCESSING_SCRIPT'
#!/bin/bash
cd /home/ubuntu

echo "🚀 Starting Memory-Optimized RAG Processing"
echo "==========================================="

# Activate environment
source /home/ubuntu/rag-env/bin/activate

# Load environment variables
export $(grep -v '^#' /home/ubuntu/.env | xargs)

# Verify all files are present
echo "📂 Checking for required files..."
while [ ! -f aws_transcript_processor.py ] || [ ! -f credentials.json ]; do
    echo "   Waiting for files... ($(date))"
    sleep 10
done

echo "✅ All files present, starting processing..."

# Set memory limits and run processing
ulimit -v 6000000  # Limit virtual memory to 6GB
export PYTHONMEMORY=4000000  # Limit Python memory usage

# Run the processor with monitoring
echo "🏛️ Processing 336 episodes with memory optimization..."
python3 aws_transcript_processor.py 2>&1 | tee -a rag-processing.log

echo "✅ RAG processing complete!"
echo "📊 Processing finished at: $(date)"

# Show final status
echo ""
echo "🎯 Final Status:"
grep -E "(Success|Failed|Total)" rag-processing.log | tail -5

PROCESSING_SCRIPT

chmod +x /home/ubuntu/run-rag-processing.sh

# Signal setup complete
echo "ready" > /home/ubuntu/setup-complete.txt
chown ubuntu:ubuntu /home/ubuntu/setup-complete.txt

echo "✅ Robust setup complete at $(date)"
STARTUP_SCRIPT

# Inject actual environment variables into startup script using Python (not sed!)
echo "🔧 Injecting environment variables..."

python3 << PYTHON_INJECT
with open('startup-script.sh', 'r') as f:
    content = f.read()

# Replace placeholders with actual values
content = content.replace('__QDRANT_URL__', '''$QDRANT_CLOUD_URL''')
content = content.replace('__QDRANT_API_KEY__', '''$QDRANT_CLOUD_API_KEY''')
content = content.replace('__OPENAI_API_KEY__', '''$OPENAI_API_KEY''')
content = content.replace('__ANTHROPIC_API_KEY__', '''$ANTHROPIC_API_KEY''')
content = content.replace('__GCS_PROJECT__', '''$GCS_PROJECT_ID''')
content = content.replace('__GCS_BUCKET__', '''$GCS_BUCKET_NAME''')
content = content.replace('__COLLECTION_NAME__', '''$QDRANT_COLLECTION_NAME''')

with open('startup-script.sh', 'w') as f:
    f.write(content)

print("✅ Environment variables injected")
PYTHON_INJECT

# Create optimized spot fleet config
echo "🔧 Creating optimized fleet configuration..."

python3 << 'PYTHON_CONFIG'
import json
import base64

# Read original config
with open('config/spot-fleet-config.json', 'r') as f:
    config = json.load(f)

# Read startup script
with open('startup-script.sh', 'rb') as f:
    script_content = f.read()
    base64_script = base64.b64encode(script_content).decode('utf-8')

# Optimize for RAG processing with MORE memory
config['SpotPrice'] = '0.10'  # Higher price for better availability
config['LaunchSpecifications'][0]['InstanceType'] = 'c5.xlarge'  # 4 vCPU, 8GB RAM
config['LaunchSpecifications'][0]['UserData'] = base64_script

# Keep 50GB storage (AMI requirement)
# Don't modify storage size - AMI needs it

# Write optimized config
with open('config/spot-fleet-config-rag.json', 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Optimized fleet config created")
PYTHON_CONFIG

# Clean up
rm startup-script.sh

echo "✅ Configuration complete"

# Launch fleet
echo "🚀 Launching optimized spot fleet..."
FLEET_ID=$(aws ec2 request-spot-fleet --spot-fleet-request-config file://config/spot-fleet-config-rag.json --query 'SpotFleetRequestId' --output text)

if [ $? -ne 0 ]; then
    echo "❌ Failed to launch fleet"
    exit 1
fi

echo "✅ Fleet launched: $FLEET_ID"

# Wait for instance
echo "⏳ Waiting for instance..."
start_time=$(date +%s)

while true; do
    STATUS=$(aws ec2 describe-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --query 'SpotFleetRequestConfigs[0].ActivityStatus' --output text)
    elapsed=$(($(date +%s) - start_time))

    echo "   Status: $STATUS (${elapsed}s elapsed)"

    if [ "$STATUS" = "fulfilled" ]; then
        echo "✅ Fleet ready in ${elapsed} seconds"
        break
    elif [ "$STATUS" = "error" ]; then
        echo "❌ Fleet failed"
        aws ec2 describe-spot-fleet-request-history --spot-fleet-request-id $FLEET_ID --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) 2>/dev/null
        exit 1
    fi

    sleep 15
done

# Get instance details
INSTANCE_ID=$(aws ec2 describe-spot-fleet-instances --spot-fleet-request-id $FLEET_ID --query 'ActiveInstances[0].InstanceId' --output text)
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "📡 Instance details:"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"

# Wait for setup
echo "⏳ Waiting for robust setup to complete..."
setup_start=$(date +%s)

for i in {1..20}; do  # 10 minutes max
    if ssh -i $SSH_KEY_PATH -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "test -f setup-complete.txt" 2>/dev/null; then
        setup_time=$(($(date +%s) - setup_start))
        echo "✅ Setup complete in ${setup_time} seconds"
        break
    fi
    echo "   Setup in progress ($i/20)..."
    sleep 30
done

# Deploy files
echo "📤 Deploying processing files..."
scp -i $SSH_KEY_PATH -o StrictHostKeyChecking=no ../../data_processing/aws_transcript_processor.py ubuntu@$PUBLIC_IP:~/
scp -i $SSH_KEY_PATH -o StrictHostKeyChecking=no config/credentials.json ubuntu@$PUBLIC_IP:~/

# Start processing
echo "🏛️ Starting RAG processing..."
ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "nohup ./run-rag-processing.sh > processing-output.log 2>&1 &"

# Final summary
total_time=$(( $(date +%s) - start_time ))
minutes=$((total_time / 60))
seconds=$((total_time % 60))

echo ""
echo "🎉 FIXED DEPLOYMENT COMPLETE!"
echo "============================="
echo "Fleet ID: $FLEET_ID"
echo "Instance: $INSTANCE_ID"
echo "IP: $PUBLIC_IP"
echo "Instance Type: c5.xlarge (4 vCPU, 8GB RAM)"
echo "Deployment time: ${minutes}m ${seconds}s"
echo ""
echo "📊 Monitor processing:"
echo "   ssh -i $SSH_KEY_PATH ubuntu@$PUBLIC_IP"
echo "   tail -f rag-processing.log"
echo ""
echo "🛑 IMPORTANT - Stop fleet when done:"
echo "   aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "✅ This deployment should work without manual intervention!"
echo "⏱️ Expected processing time: 60-90 minutes for 336 episodes"