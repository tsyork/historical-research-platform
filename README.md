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
