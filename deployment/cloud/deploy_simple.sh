#!/bin/bash

# Simple Cloud Run Deployment Script
# Deploys without Secret Manager for faster initial setup

echo "🚀 Deploying Historical Research Platform to Cloud Run"
echo "======================================================"

# Check if required files exist
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found. Please create it first."
    exit 1
fi

if [ ! -f "src/main.py" ]; then
    echo "❌ src/main.py not found. Please create it first."
    exit 1
fi

# Set project variables
PROJECT_ID="podcast-transcription-462218"
SERVICE_NAME="historical-research-platform"
REGION="us-central1"

echo "📋 Project: $PROJECT_ID"
echo "📋 Service: $SERVICE_NAME"
echo "📋 Region: $REGION"

# Deploy with environment variables directly (no secrets for now)
echo "🔨 Building and deploying to Cloud Run..."

gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars="QDRANT_CLOUD_URL=https://490b7930-5b68-43c1-af19-1041e7081f46.us-west-1-0.aws.cloud.qdrant.io:6333,QDRANT_COLLECTION_NAME=historical_sources,ENVIRONMENT=production,QDRANT_CLOUD_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.25P7kz8h609_Vab-hLscD4nn8zj9gO3ZNiFvGubG9LE,ANTHROPIC_API_KEY=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,OPENAI_API_KEY=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" \
  --project $PROJECT_ID

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Your application should be available at:"
echo "https://$SERVICE_NAME-[random-hash]-uc.a.run.app"
echo ""
echo "Check the deployment status:"
echo "gcloud run services describe $SERVICE_NAME --region $REGION"