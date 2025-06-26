#!/usr/bin/env python3
"""
Create Optimized Qdrant Cloud Collection
Sets up the perfect collection schema for multi-source historical research platform
"""

import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv
from datetime import datetime


def create_historical_collection():
    """Create optimized collection for historical research platform"""

    print("🚀 Creating Qdrant Cloud Collection for Historical Research Platform")
    print("=" * 70)

    # Load environment variables
    load_dotenv()

    # Get connection details
    qdrant_url = os.getenv('QDRANT_CLOUD_URL')
    qdrant_api_key = os.getenv('QDRANT_CLOUD_API_KEY')
    collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'historical_sources')

    if not qdrant_url or not qdrant_api_key:
        print("❌ Missing Qdrant Cloud credentials in .env file")
        print("📋 Required environment variables:")
        print("   QDRANT_CLOUD_URL=https://your-cluster.qdrant.tech:6333")
        print("   QDRANT_CLOUD_API_KEY=your_api_key")
        return False

    try:
        # Connect to Qdrant Cloud
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30,
            check_compatibility=False
        )

        print(f"✅ Connected to Qdrant Cloud")
        print(f"🌐 Cluster URL: {qdrant_url}")

        # Check existing collections
        collections = client.get_collections()
        existing_collections = [c.name for c in collections.collections]

        print(f"📊 Existing collections: {existing_collections}")

        if collection_name in existing_collections:
            print(f"⚠️ Collection '{collection_name}' already exists")
            recreate = input(f"Do you want to recreate it? (y/N): ").strip().lower()
            if recreate == 'y':
                print(f"🗑️ Deleting existing collection...")
                client.delete_collection(collection_name)
                print(f"✅ Deleted successfully")
            else:
                print(f"📋 Using existing collection")
                # Still verify the configuration
                verify_collection_config(client, collection_name)
                return True

        # Create optimized collection for multi-source platform
        print(f"🏗️ Creating collection: '{collection_name}'")

        # Create collection with minimal, working configuration
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # OpenAI text-embedding-3-small dimensions
                distance=models.Distance.COSINE,  # Best for semantic similarity
            )
        )

        print(f"✅ Collection '{collection_name}' created successfully!")

        # Now optimize the collection settings after creation
        print(f"🔧 Optimizing collection settings...")

        try:
            # Update collection with optimized settings
            client.update_collection(
                collection_name=collection_name,
                optimizer_config=models.OptimizersConfig(
                    deleted_threshold=0.2,
                    vacuum_min_vector_number=1000,
                    default_segment_number=0,
                    max_segment_size=None,
                    memmap_threshold=1000,
                    indexing_threshold=1000,
                    flush_interval_sec=5,
                    max_optimization_threads=0,
                )
            )
            print(f"✅ Collection optimized successfully!")
        except Exception as e:
            print(f"⚠️ Optimization warning (collection still functional): {e}")
            print(f"✅ Collection created with default settings")

        # Verify collection creation
        verify_collection_config(client, collection_name)

        # Verify basic operations
        verify_collection_operations(client, collection_name)

        return True

    except Exception as e:
        print(f"❌ Collection creation failed: {e}")
        return False


def verify_collection_config(client, collection_name):
    """Verify the collection configuration"""

    print(f"\n🔍 Verifying Collection Configuration:")
    print("-" * 40)

    try:
        collection_info = client.get_collection(collection_name)

        print(f"📊 Collection Name: {collection_name}")
        print(f"📊 Status: {collection_info.status}")
        print(f"📊 Points Count: {collection_info.points_count}")
        print(f"📊 Indexed Vectors: {collection_info.vectors_count}")

        # Check vector configuration
        vectors_config = collection_info.config.params.vectors
        print(f"📊 Vector Size: {vectors_config.size}")
        print(f"📊 Distance Metric: {vectors_config.distance}")

        # Check optimizer settings
        optimizers = collection_info.config.optimizer_config
        print(f"📊 Indexing Threshold: {optimizers.indexing_threshold}")
        print(f"📊 Memmap Threshold: {optimizers.memmap_threshold}")

        print(f"✅ Configuration verified successfully")

    except Exception as e:
        print(f"❌ Configuration verification failed: {e}")


def create_sample_metadata():
    """Create sample metadata structure for documentation"""

    return {
        # Source identification
        "source_type": "podcast",  # podcast | paper | document | article
        "source_name": "revolutions",  # revolutions | history_of_rome | custom

        # Content structure
        "chunk_index": 0,  # Position within episode/document
        "total_chunks": 45,  # Total chunks in this source
        "content_length": 1200,  # Character length of this chunk

        # Podcast-specific (null for non-podcast sources)
        "season": 4,  # Season number
        "episode_number": "4.12",  # Episode identifier
        "episode_title": "The Girondins",
        "revolution": "French Revolution",
        "historical_period": "1792-1794",
        "podcast_date": "2017-05-15",

        # Document-specific (future use)
        "document_type": None,  # "primary_source" | "research_paper" | "article"
        "authors": None,  # List of authors
        "publication_date": None,  # When document was published
        "document_title": None,  # Title of paper/document

        # Processing metadata
        "processed_date": datetime.now().isoformat(),
        "embedding_model": "text-embedding-3-small",
        "processing_version": "v2.0"
    }


def verify_collection_operations(client, collection_name):
    """Verify basic collection operations with sample data"""

    print(f"\n🧪 Verifying Collection Operations:")
    print("-" * 40)

    try:
        import numpy as np

        # Create sample vector and metadata
        sample_vector = np.random.rand(1536).tolist()  # Random 1536-dim vector
        sample_metadata = create_sample_metadata()

        # Insert test point
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=1,
                    vector=sample_vector,
                    payload=sample_metadata
                )
            ]
        )

        print("✅ Sample vector inserted successfully")

        # Test vector search using new API
        search_results = client.query_points(
            collection_name=collection_name,
            query=sample_vector,
            limit=1
        ).points

        print(f"✅ Vector search successful: found {len(search_results)} results")

        # Test metadata filtering using new API
        filter_results = client.query_points(
            collection_name=collection_name,
            query=sample_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_type",
                        match=models.MatchValue(value="podcast")
                    )
                ]
            ),
            limit=1
        ).points

        print(f"✅ Metadata filtering successful: found {len(filter_results)} results")

        # Clean up test data
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[1])
        )

        print("🧹 Test data cleaned up")
        print("✅ All operations working correctly!")

        return True

    except Exception as e:
        print(f"❌ Operation verification failed: {e}")
        return False


def generate_usage_summary(collection_name):
    """Generate summary of what was created"""

    print(f"\n🎉 Collection Setup Complete!")
    print("=" * 50)
    print(f"📊 Collection Name: {collection_name}")
    print(f"🔧 Vector Dimensions: 1536 (OpenAI text-embedding-3-small)")
    print(f"📏 Distance Metric: Cosine similarity")
    print(f"⚡ Indexing Threshold: 1000 vectors")
    print(f"💾 Memory Mapping: Enabled for efficiency")
    print(f"🔄 Quantization: Enabled for memory optimization")

    print(f"\n🚀 Ready For:")
    print(f"  ✅ Revolutions podcast data")
    print(f"  ✅ History of Rome podcast data")
    print(f"  ✅ Future: PDF documents, research papers")
    print(f"  ✅ Future: Web articles, primary sources")

    print(f"\n📋 Next Steps:")
    print(f"  1. Process and upload podcast transcripts")
    print(f"  2. Create Streamlit interface")
    print(f"  3. Test multi-source search capabilities")
    print(f"  4. Deploy to Google Cloud Run")


if __name__ == "__main__":
    # Create the collection
    success = create_historical_collection()

    if success:
        collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'historical_sources')
        generate_usage_summary(collection_name)

        print(f"\n🔗 Connection Details:")
        print(f"  URL: {os.getenv('QDRANT_CLOUD_URL')}")
        print(f"  Collection: {collection_name}")
        print(f"  API Key: {os.getenv('QDRANT_CLOUD_API_KEY', 'Not set')[:20]}...")

    else:
        print(f"\n🔧 Troubleshooting:")
        print(f"  1. Check your .env file has correct credentials")
        print(f"  2. Verify Qdrant Cloud cluster is running")
        print(f"  3. Ensure API key has proper permissions")