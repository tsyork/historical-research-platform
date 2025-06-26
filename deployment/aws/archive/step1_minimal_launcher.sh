#!/bin/bash

# Step 1: Minimal AWS Spot Fleet Launcher
# This script ONLY launches an instance and verifies SSH connectivity
# NO environment variables, NO file deployment, NO processing yet

set -e

echo "🔧 Step 1: Minimal Spot Fleet Test"
echo "================================="

# Verify required files exist
if [ ! -f "deployment/aws/config/whisper-transcription-key.pem" ]; then
    echo "❌ Missing SSH key: deployment/aws/config/whisper-transcription-key.pem"
    exit 1
fi

if [ ! -f "deployment/aws/config/spot-fleet-config.json" ]; then
    echo "❌ Missing fleet config: deployment/aws/config/spot-fleet-config.json"
    exit 1
fi

# Test AWS CLI access
echo "🔑 Testing AWS CLI access..."
aws sts get-caller-identity > /dev/null || {
    echo "❌ AWS CLI not configured or no access"
    exit 1
}
echo "✅ AWS CLI access confirmed"

# Launch spot fleet
echo "🚀 Launching minimal spot fleet..."
cd deployment/aws/config
FLEET_ID=$(aws ec2 request-spot-fleet --spot-fleet-request-config file://spot-fleet-config.json --query 'SpotFleetRequestId' --output text)

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

# Test SSH connectivity
echo "🔌 Testing SSH connectivity..."
max_ssh_attempts=15
ssh_attempt=0

while [ $ssh_attempt -lt $max_ssh_attempts ]; do
    echo "   SSH attempt $((ssh_attempt+1))/$max_ssh_attempts..."

    if ssh -i whisper-transcription-key.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP "echo 'SSH connection successful'" 2>/dev/null; then
        echo "✅ SSH connectivity confirmed!"
        break
    fi

    sleep 20
    ssh_attempt=$((ssh_attempt+1))
done

if [ $ssh_attempt -eq $max_ssh_attempts ]; then
    echo "❌ SSH connectivity failed after $max_ssh_attempts attempts"
    echo "💡 Instance may still be starting. Try manual SSH:"
    echo "   ssh -i deployment/aws/config/whisper-transcription-key.pem ubuntu@$PUBLIC_IP"
    exit 1
fi

# Success summary
echo ""
echo "🎉 Step 1 SUCCESSFUL - Minimal fleet deployment working!"
echo "========================================================"
echo "Fleet ID: $FLEET_ID"
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo ""
echo "Manual SSH command:"
echo "ssh -i deployment/aws/config/whisper-transcription-key.pem ubuntu@$PUBLIC_IP"
echo ""
echo "To terminate:"
echo "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids $FLEET_ID --terminate-instances"
echo ""
echo "🔄 Ready for Step 2: Environment variable injection"