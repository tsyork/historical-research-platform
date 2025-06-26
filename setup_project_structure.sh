#!/bin/bash

# Project Structure Recreation Script
# Recreates the directory structure that was lost

echo "🏗️ Recreating Historical Research Platform Project Structure"
echo "=========================================================="

# Create main project directories
echo "📁 Creating main directories..."
mkdir -p src
mkdir -p data_processing
mkdir -p deployment/aws/config
mkdir -p scripts
mkdir -p tests
mkdir -p docs

echo "✅ Directory structure created"

# Create placeholder files to maintain git structure
echo "📄 Creating placeholder files..."

# Create __init__.py files for Python packages
touch src/__init__.py
touch data_processing/__init__.py
touch tests/__init__.py

# Create basic .gitignore
cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/

# Virtual environments
.venv/
venv/
env/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Sensitive deployment files
deployment/aws/config/credentials.json
deployment/aws/config/*.pem
deployment/aws/config/spot-fleet-config*.json

# Log files
*.log
logs/

# Temporary files
*.tmp
*~
.#*
EOF

# Create .env.example template
cat > .env.example << 'EOF'
# Qdrant Cloud Configuration
QDRANT_CLOUD_URL=https://your-cluster.qdrant.tech:6333
QDRANT_CLOUD_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION_NAME=historical_sources

# AI Service API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key

# Google Cloud Configuration
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
GCS_PROJECT_ID=podcast-transcription-462218
GCS_BUCKET_NAME=ai_knowledgebase
GOOGLE_DRIVE_FOLDER_ID=136Nmn3gJe0DPVh8p4vUl3oD4-qDNRySh

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF

# Create basic requirements.txt
cat > requirements.txt << 'EOF'
# Core dependencies
streamlit>=1.28.0
anthropic>=0.8.0
openai>=1.0.0
qdrant-client>=1.7.0

# Google Cloud integration
google-cloud-storage>=2.10.0
google-api-python-client>=2.100.0
google-auth>=2.23.0

# Data processing
pandas>=2.0.0
numpy>=1.24.0
python-dotenv>=1.0.0

# Visualization
plotly>=5.17.0
matplotlib>=3.7.0

# Development tools
pytest>=7.4.0
black>=23.0.0
flake8>=6.0.0

# Production
gunicorn>=21.2.0
EOF

# Create README.md
cat > README.md << 'EOF'
# Historical Research Platform

AI-powered multi-source historical research platform with advanced analysis capabilities.

## Features

- **Multi-source Analysis**: Search across podcast transcripts, research papers, and primary sources
- **AI-Powered Insights**: Advanced historical analysis using Claude and OpenAI
- **Vector Search**: Semantic search across historical content using Qdrant
- **Cloud Deployment**: Scalable deployment on Google Cloud Run
- **Extensible Architecture**: Easy integration of new historical sources

## Quick Start

1. **Setup Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run Local Development**:
   ```bash
   streamlit run src/main.py
   ```

## Project Structure

- `src/` - Streamlit web application
- `data_processing/` - Data processing and RAG pipeline
- `deployment/` - AWS and GCP deployment scripts
- `scripts/` - Utility scripts for setup and maintenance
- `tests/` - Test suite

## Live Platform

Production deployment: https://historical-research-platform-320103070676.us-central1.run.app

## License

MIT License
EOF

echo "✅ Basic project files created"

# Create basic file structure summary
echo ""
echo "📋 Project Structure Created:"
echo "historical-research-platform/"
echo "├── .env.example"
echo "├── .gitignore"
echo "├── README.md"
echo "├── requirements.txt"
echo "├── src/"
echo "│   └── __init__.py"
echo "├── data_processing/"
echo "│   └── __init__.py"
echo "├── deployment/"
echo "│   └── aws/"
echo "│       └── config/"
echo "├── scripts/"
echo "├── tests/"
echo "│   └── __init__.py"
echo "└── docs/"
echo ""
echo "🎯 Next Steps:"
echo "1. Copy your actual API keys to .env (from .env.example)"
echo "2. Copy code from chat artifacts to the appropriate files"
echo "3. Add your credentials to deployment/aws/config/"
echo "4. Activate virtual environment and install dependencies"
echo ""
echo "💡 To install dependencies:"
echo "source .venv/bin/activate"
echo "pip install -r requirements.txt"
echo ""
echo "✅ Project structure recreation complete!"