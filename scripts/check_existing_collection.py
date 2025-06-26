#!/usr/bin/env python3
"""
Check Existing Qdrant Cloud Collection
Verify if your existing collection is suitable for the multi-source platform
"""

import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv


def check_existing_collection():
    """Check your existing Qdrant Cloud collection configuration"""

    print("🔍 Checking Existing Qdrant Cloud Collection")
    print("=" * 50)

    # Load environment variables
    load_dotenv()

    # Get connection details
    qdrant_url = os.getenv('QDRANT_CLOUD_URL')
    qdrant_api_key = os.getenv('QDRANT_CLOUD_API_KEY')

    if not qdrant_url or not qdrant_api_key:
        print("❌ Missing Qdrant Cloud credentials in .env file")
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
        print(f"🌐 URL: {qdrant_url}")

        # Get all collections
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]

        print(f"\n📊 Available Collections:")
        for i, name in enumerate(collection_names, 1):
            print(f"  {i}. {name}")

        if not collection_names:
            print("❌ No collections found")
            return False

        # Check each collection
        for collection_name in collection_names:
            print(f"\n🔍 Analyzing Collection: '{collection_name}'")
            print("-" * 40)

            # Get collection info
            collection_info = client.get_collection(collection_name)

            print(f"📊 Status: {collection_info.status}")
            print(f"📊 Points: {collection_info.points_count}")
            print(f"📊 Indexed Vectors: {collection_info.vectors_count}")

            # Check vector configuration
            vectors_config = collection_info.config.params.vectors
            if hasattr(vectors_config, 'size'):
                vector_size = vectors_config.size
                distance = vectors_config.distance
                print(f"📊 Vector Size: {vector_size}")
                print(f"📊 Distance Metric: {distance}")
            else:
                print("📊 Vector Config: Multiple vectors or complex config")

            # Check optimizer settings
            optimizers = collection_info.config.optimizer_config
            print(f"📊 Indexing Threshold: {optimizers.indexing_threshold}")
            print(f"📊 Memmap Threshold: {optimizers.memmap_threshold}")

            # Sample some points to check metadata structure
            if collection_info.points_count > 0:
                print(f"\n🔍 Sample Data Structure:")
                try:
                    # Get a few sample points
                    sample_points = client.scroll(
                        collection_name=collection_name,
                        limit=3,
                        with_payload=True,
                        with_vectors=False
                    )[0]

                    for i, point in enumerate(sample_points):
                        print(f"\n  Sample Point {i + 1}:")
                        print(f"    ID: {point.id}")
                        if point.payload:
                            print(f"    Metadata keys: {list(point.payload.keys())}")
                            # Show sample metadata structure
                            for key, value in list(point.payload.items())[:5]:
                                print(f"      {key}: {value}")
                        else:
                            print(f"    No metadata found")

                except Exception as e:
                    print(f"    ❌ Could not sample data: {e}")

            # Evaluate suitability for multi-source platform
            print(f"\n✅ Suitability Assessment:")

            suitable = True
            issues = []
            recommendations = []

            # Check vector size (should be 1536 for OpenAI embeddings)
            if hasattr(vectors_config, 'size') and vectors_config.size != 1536:
                suitable = False
                issues.append(f"Vector size is {vectors_config.size}, need 1536 for OpenAI embeddings")

            # Check distance metric (should be Cosine)
            if hasattr(vectors_config, 'distance') and vectors_config.distance != models.Distance.COSINE:
                issues.append(f"Distance metric is {vectors_config.distance}, Cosine is recommended")

            # Check indexing threshold
            if optimizers.indexing_threshold > 5000:
                recommendations.append("Lower indexing threshold for faster search")

            # Check if collection has data
            if collection_info.points_count == 0:
                recommendations.append("Collection is empty - ready for data upload")
            elif collection_info.points_count > 0:
                recommendations.append("Collection has existing data - check compatibility")

            if suitable and not issues:
                print(f"    ✅ SUITABLE for multi-source platform")
            else:
                print(f"    ⚠️ NEEDS MODIFICATION for optimal performance")

            if issues:
                print(f"    🚨 Issues:")
                for issue in issues:
                    print(f"      - {issue}")

            if recommendations:
                print(f"    💡 Recommendations:")
                for rec in recommendations:
                    print(f"      - {rec}")

        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def recommend_next_steps():
    """Provide recommendations based on collection analysis"""

    print(f"\n🎯 Next Steps Recommendations:")
    print("=" * 50)

    print(f"📋 Option 1: Use Existing Collection")
    print(f"  ✅ If collection is suitable (1536 vectors, Cosine distance)")
    print(f"  ✅ If metadata structure is compatible")
    print(f"  ✅ Save time and use what you have")

    print(f"\n📋 Option 2: Optimize Existing Collection")
    print(f"  🔧 Adjust indexing thresholds")
    print(f"  🔧 Add missing metadata fields")
    print(f"  🔧 Keep existing data, improve performance")

    print(f"\n📋 Option 3: Create New Optimized Collection")
    print(f"  🆕 Start fresh with perfect configuration")
    print(f"  🆕 Unified metadata schema for multi-source")
    print(f"  🆕 Optimal performance settings")

    print(f"\n💡 My Recommendation:")
    print(f"  Run this analysis first, then decide based on results")
    print(f"  If existing collection is close to optimal → use it")
    print(f"  If it needs major changes → create new one")


if __name__ == "__main__":
    # Check existing collection
    success = check_existing_collection()

    if success:
        recommend_next_steps()
    else:
        print(f"\n🔧 Setup Required:")
        print(f"  1. Ensure .env file has correct Qdrant Cloud credentials")
        print(f"  2. Verify Qdrant Cloud cluster is running")
        print(f"  3. Check API key permissions")