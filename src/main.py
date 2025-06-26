#!/usr/bin/env python3
"""
Historical Research Platform - Main Streamlit Application
AI-powered multi-source historical research with advanced analysis capabilities
"""

import streamlit as st
import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def init_app():
    """Initialize the Streamlit application"""
    st.set_page_config(
        page_title="Historical Research Platform",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        padding: 1rem 0;
        border-bottom: 1px solid #e6e6e6;
        margin-bottom: 2rem;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    </style>
    """, unsafe_allow_html=True)


@st.cache_resource
def init_qdrant_client():
    """Initialize Qdrant client with caching"""
    try:
        client = QdrantClient(
            url=os.getenv('QDRANT_CLOUD_URL'),
            api_key=os.getenv('QDRANT_CLOUD_API_KEY'),
            timeout=30,
            check_compatibility=False
        )

        # Test connection
        collections = client.get_collections()
        logger.info(f"Connected to Qdrant Cloud: {len(collections.collections)} collections")

        return client, collections.collections

    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        return None, None


def display_header():
    """Display main application header"""
    st.markdown('<div class="main-header">', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("🏛️ Historical Research Platform")
        st.markdown("**AI-powered multi-source historical analysis with advanced research capabilities**")

    with col2:
        st.markdown(f"**Environment:** {os.getenv('ENVIRONMENT', 'development').title()}")
        st.markdown(f"**Version:** 1.0.0")
        st.markdown(f"**Updated:** {datetime.now().strftime('%Y-%m-%d')}")

    st.markdown('</div>', unsafe_allow_html=True)


def display_system_status():
    """Display system status and connection information"""
    st.markdown("## 🔧 System Status")

    # Initialize Qdrant connection
    client, collections = init_qdrant_client()

    col1, col2 = st.columns(2)

    with col1:
        if client:
            st.markdown('<div class="status-box success-box">', unsafe_allow_html=True)
            st.markdown("### ✅ Qdrant Cloud Connected")
            st.markdown(f"**Collections Available:** {len(collections)}")
            for collection in collections:
                try:
                    info = client.get_collection(collection.name)
                    st.markdown(f"- **{collection.name}**: {info.points_count:,} vectors")
                except:
                    st.markdown(f"- **{collection.name}**: Status unknown")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-box error-box">', unsafe_allow_html=True)
            st.markdown("### ❌ Qdrant Cloud Connection Failed")
            st.markdown("Please check configuration and network connectivity")
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("### 🌐 Configuration")
        st.markdown(f"**Qdrant URL:** `{os.getenv('QDRANT_CLOUD_URL', 'Not configured')[:50]}...`")
        st.markdown(f"**Collection:** `{os.getenv('QDRANT_COLLECTION_NAME', 'historical_sources')}`")
        st.markdown(f"**API Keys:** {'✅ Configured' if os.getenv('ANTHROPIC_API_KEY') else '❌ Missing'}")


def display_query_interface():
    """Display the main query interface"""
    st.markdown("## 🔍 Historical Research Interface")

    # Query input
    col1, col2 = st.columns([3, 1])

    with col1:
        query = st.text_area(
            "Enter your historical research question:",
            placeholder="Examples:\n- What were the economic causes of the French Revolution?\n- Compare leadership styles in revolutionary movements\n- How did communication methods affect revolutionary outcomes?",
            height=100
        )

    with col2:
        st.markdown("### Query Options")

        query_type = st.selectbox(
            "Analysis Type:",
            ["General Analysis", "Comparative Study", "Thematic Research", "Character Analysis", "Timeline Analysis"]
        )

        source_filter = st.multiselect(
            "Source Filter:",
            ["Revolutions Podcast", "History of Rome", "Research Papers", "Primary Sources"],
            default=[]
        )

        max_results = st.slider("Max Results:", 5, 50, 15)

    # Query processing
    if st.button("🚀 Analyze", type="primary"):
        if query.strip():
            with st.spinner("Processing your historical research query..."):
                process_query(query, query_type, source_filter, max_results)
        else:
            st.warning("Please enter a research question")


def process_query(query, query_type, source_filter, max_results):
    """Process the user query (placeholder for now)"""
    st.markdown("### 📊 Query Results")

    # Placeholder results
    st.info("🚧 **Query Processing System Under Development**")

    st.markdown(f"**Your Question:** {query}")
    st.markdown(f"**Analysis Type:** {query_type}")
    st.markdown(f"**Source Filters:** {', '.join(source_filter) if source_filter else 'All sources'}")
    st.markdown(f"**Max Results:** {max_results}")

    # Mock results display
    with st.expander("🔍 Search Results Preview"):
        st.markdown("""
        **Coming Soon:**
        - Vector search across historical sources
        - AI-powered analysis and synthesis
        - Source attribution and citations
        - Comparative analysis capabilities
        - Timeline and relationship mapping
        """)


def display_sidebar():
    """Display sidebar with additional information"""
    with st.sidebar:
        st.markdown("## 📚 About This Platform")

        st.markdown("""
        This platform provides AI-powered analysis of historical sources including:

        **📻 Podcast Sources:**
        - Revolutions Podcast (10+ seasons)
        - History of Rome (179+ episodes)

        **📄 Document Sources:**
        - Research papers
        - Primary source materials
        - Historical analyses

        **🔍 Analysis Capabilities:**
        - Semantic search across sources
        - Comparative historical analysis
        - Character and theme tracking
        - Timeline reconstruction
        """)

        st.markdown("---")

        st.markdown("## 🔧 Technical Details")
        st.markdown(f"""
        **Vector Database:** Qdrant Cloud  
        **AI Models:** Claude Sonnet 4, OpenAI  
        **Deployment:** Google Cloud Run  
        **Processing:** Real-time analysis  
        """)

        if st.button("📊 View System Metrics"):
            st.info("Detailed metrics will be available in the next update")


def main():
    """Main application function"""
    try:
        # Initialize app
        init_app()

        # Display sidebar
        display_sidebar()

        # Main content
        display_header()
        display_system_status()

        st.markdown("---")

        display_query_interface()

        # Footer
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #666; padding: 2rem 0;'>
            Historical Research Platform v1.0 | 
            Powered by AI | 
            <a href='https://github.com/yourusername/historical-research-platform' target='_blank'>View Source</a>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}")


if __name__ == "__main__":
    main()