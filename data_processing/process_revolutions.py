#!/usr/bin/env python3
"""
Data Processor: Revolutions Podcast to Qdrant Cloud
Processes existing Google Drive transcripts and uploads to Qdrant Cloud collection
"""

import os
import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path

# Core libraries
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# Google Cloud integration
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import storage

# AI libraries
import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


class RevolutionsDataProcessor:
    """Process Revolutions podcast transcripts for Qdrant Cloud upload"""

    def __init__(self):
        """Initialize the data processor"""

        # Configuration
        self.gcs_project = os.getenv('GCS_PROJECT_ID', 'podcast-transcription-462218')
        self.gcs_bucket = os.getenv('GCS_BUCKET_NAME', 'ai_knowledgebase')
        self.gcs_metadata_prefix = 'podcasts/revolutions/metadata/'

        # Qdrant Cloud configuration
        self.qdrant_url = os.getenv('QDRANT_CLOUD_URL')
        self.qdrant_api_key = os.getenv('QDRANT_CLOUD_API_KEY')
        self.collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'historical_sources')

        # OpenAI configuration
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Google credentials
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')

        # Processing settings
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Character overlap between chunks

        # Initialize clients
        self._init_clients()

        # Revolution mapping for metadata
        self.revolution_mapping = {
            1: "English Civil War",
            2: "American Revolution",
            3: "French Revolution",
            4: "Haitian Revolution",
            5: "Spanish American Wars of Independence",
            6: "July Revolution & Revolutions of 1830",
            7: "German Revolution of 1848",
            8: "Paris Commune",
            9: "Mexican Revolution",
            10: "Russian Revolution"
        }

    def _init_clients(self):
        """Initialize API clients"""

        # Google API clients
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=[
                    "https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/documents.readonly",
                    "https://www.googleapis.com/auth/cloud-platform"
                ]
            )

            self.drive_service = build('drive', 'v3', credentials=credentials)
            self.docs_service = build('docs', 'v1', credentials=credentials)
            self.gcs_client = storage.Client(credentials=credentials, project=self.gcs_project)

            logger.info("✅ Google API clients initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google clients: {e}")
            raise

        # OpenAI client
        try:
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
            logger.info("✅ OpenAI client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            raise

        # Qdrant client
        try:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=60,
                check_compatibility=False
            )

            # Test connection
            collections = self.qdrant_client.get_collections()
            logger.info(f"✅ Qdrant client initialized: {len(collections.collections)} collections")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Qdrant client: {e}")
            raise

    def get_metadata_files(self) -> List[Dict]:
        """Get all metadata files from Google Cloud Storage"""

        logger.info("📂 Fetching metadata files from Google Cloud Storage...")

        try:
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            blobs = bucket.list_blobs(prefix=self.gcs_metadata_prefix)

            metadata_files = []
            for blob in blobs:
                if blob.name.endswith('.json'):
                    try:
                        content = blob.download_as_text()
                        metadata = json.loads(content)
                        metadata['gcs_path'] = blob.name
                        metadata_files.append(metadata)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse {blob.name}: {e}")

            logger.info(f"📊 Found {len(metadata_files)} metadata files")
            return metadata_files

        except Exception as e:
            logger.error(f"❌ Failed to fetch metadata files: {e}")
            return []

    def get_google_doc_content(self, doc_id: str) -> Optional[str]:
        """Retrieve content from Google Doc"""

        try:
            doc = self.docs_service.documents().get(documentId=doc_id).execute()

            content = ""
            for element in doc.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    for text_element in paragraph.get('elements', []):
                        if 'textRun' in text_element:
                            content += text_element['textRun']['content']

            return content.strip()

        except Exception as e:
            logger.error(f"❌ Failed to fetch Google Doc {doc_id}: {e}")
            return None

    def extract_transcript_content(self, full_content: str) -> str:
        """Extract transcript content from formatted document"""

        # Remove metadata header (everything before and including ---)
        parts = full_content.split('---')
        if len(parts) >= 3:
            # Content after second ---
            transcript = '---'.join(parts[2:]).strip()
        else:
            # Fallback: use full content
            transcript = full_content

        return transcript

    def chunk_text(self, text: str, episode_metadata: Dict) -> List[Dict]:
        """Split text into overlapping chunks with metadata"""

        chunks = []
        text_length = len(text)

        if text_length <= self.chunk_size:
            # Single chunk
            chunks.append({
                'content': text,
                'chunk_index': 0,
                'total_chunks': 1,
                'content_length': text_length,
                **episode_metadata
            })
            return chunks

        # Multiple chunks
        chunk_count = 0
        start = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Try to break at sentence boundary
            if end < text_length:
                # Look for sentence endings within overlap region
                search_start = max(end - self.chunk_overlap, start + self.chunk_size // 2)
                sentence_end = -1

                for sentence_char in ['. ', '! ', '? ']:
                    pos = text.rfind(sentence_char, search_start, end)
                    if pos > sentence_end:
                        sentence_end = pos + len(sentence_char)

                if sentence_end > 0:
                    end = sentence_end

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_count,
                    'total_chunks': 0,  # Will update after processing all chunks
                    'content_length': len(chunk_text),
                    **episode_metadata
                })
                chunk_count += 1

            # Move start position with overlap
            start = end - self.chunk_overlap

        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total_chunks

        return chunks

    def create_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding using OpenAI API"""

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"❌ Failed to create embedding: {e}")
            return None

    def prepare_episode_metadata(self, metadata: Dict) -> Dict:
        """Prepare episode metadata for Qdrant storage"""

        season = metadata.get('season', 0)
        episode_num = metadata.get('episode_number', '0')

        return {
            # Source identification
            'source_type': 'podcast',
            'source_name': 'revolutions',

            # Podcast-specific metadata
            'season': season,
            'episode_number': episode_num,
            'episode_title': metadata.get('title', 'Unknown'),
            'revolution': self.revolution_mapping.get(season, 'Unknown Revolution'),
            'historical_period': self._get_historical_period(season),
            'podcast_date': metadata.get('published', ''),

            # Processing metadata
            'processed_date': datetime.now().isoformat(),
            'embedding_model': 'text-embedding-3-small',
            'processing_version': 'v2.0',
            'google_doc_id': metadata.get('google_doc_id', ''),
            'google_doc_url': metadata.get('google_doc_url', '')
        }

    def _get_historical_period(self, season: int) -> str:
        """Get historical period for season"""

        periods = {
            1: "1640-1660",  # English Civil War
            2: "1765-1783",  # American Revolution
            3: "1789-1799",  # French Revolution
            4: "1791-1804",  # Haitian Revolution
            5: "1808-1833",  # Spanish American Wars
            6: "1830-1831",  # July Revolution
            7: "1848-1849",  # German Revolution
            8: "1871",  # Paris Commune
            9: "1910-1920",  # Mexican Revolution
            10: "1917-1923"  # Russian Revolution
        }

        return periods.get(season, "Unknown")

    def upload_to_qdrant(self, chunks: List[Dict]) -> bool:
        """Upload chunks to Qdrant Cloud collection"""

        if not chunks:
            return True

        try:
            points = []

            for i, chunk in enumerate(chunks):
                # Create embedding
                embedding = self.create_embedding(chunk['content'])
                if not embedding:
                    logger.warning(f"⚠️ Skipping chunk {i}: embedding failed")
                    continue

                # Prepare payload (remove content from metadata)
                payload = {k: v for k, v in chunk.items() if k != 'content'}

                # Create point
                point_id = len(points) + 1  # Simple incremental ID
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                )

            if points:
                # Upload to Qdrant
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )

                logger.info(f"✅ Uploaded {len(points)} chunks to Qdrant")
                return True
            else:
                logger.warning("⚠️ No valid chunks to upload")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to upload to Qdrant: {e}")
            return False

    def process_episode(self, metadata: Dict) -> bool:
        """Process a single episode"""

        episode_id = f"{metadata.get('season', 0)}.{metadata.get('episode_number', '0')}"
        title = metadata.get('title', 'Unknown')

        logger.info(f"📻 Processing episode {episode_id}: {title}")

        # Get Google Doc content
        doc_id = metadata.get('google_doc_id')
        if not doc_id:
            logger.warning(f"⚠️ No Google Doc ID for episode {episode_id}")
            return False

        content = self.get_google_doc_content(doc_id)
        if not content:
            logger.warning(f"⚠️ Failed to get content for episode {episode_id}")
            return False

        # Extract transcript content
        transcript = self.extract_transcript_content(content)
        if not transcript:
            logger.warning(f"⚠️ No transcript content found for episode {episode_id}")
            return False

        # Prepare episode metadata
        episode_metadata = self.prepare_episode_metadata(metadata)

        # Create chunks
        chunks = self.chunk_text(transcript, episode_metadata)
        if not chunks:
            logger.warning(f"⚠️ No chunks created for episode {episode_id}")
            return False

        # Upload to Qdrant
        success = self.upload_to_qdrant(chunks)

        if success:
            logger.info(f"✅ Episode {episode_id} processed successfully ({len(chunks)} chunks)")
        else:
            logger.error(f"❌ Failed to process episode {episode_id}")

        return success

    def process_all_episodes(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Process all episodes in the metadata"""

        logger.info("🚀 Starting batch processing of Revolutions podcast episodes")

        # Get metadata files
        metadata_files = self.get_metadata_files()

        if not metadata_files:
            logger.error("❌ No metadata files found")
            return {'total': 0, 'success': 0, 'failed': 0}

        # Apply limit if specified
        if limit:
            metadata_files = metadata_files[:limit]
            logger.info(f"📋 Processing limited to {limit} episodes")

        # Sort by season and episode
        metadata_files.sort(key=lambda x: (x.get('season', 0), x.get('episode_number', '0')))

        # Process episodes
        stats = {'total': len(metadata_files), 'success': 0, 'failed': 0}

        for metadata in tqdm(metadata_files, desc="Processing episodes"):
            try:
                if self.process_episode(metadata):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            except Exception as e:
                logger.error(f"❌ Error processing episode: {e}")
                stats['failed'] += 1

        # Summary
        logger.info(f"🎉 Processing complete!")
        logger.info(f"📊 Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")

        return stats


def main():
    """Main function"""

    print("🏛️ Historical Research Platform - Data Processor")
    print("Processing Revolutions podcast transcripts for Qdrant Cloud")
    print("=" * 60)

    # Initialize processor
    try:
        processor = RevolutionsDataProcessor()
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return

    # Processing options
    print("\n📋 Processing Options:")
    print("1. Process all episodes")
    print("2. Process limited number (for testing)")
    print("3. Process single episode")

    choice = input("\nSelect option (1-3): ").strip()

    if choice == '1':
        # Process all episodes
        stats = processor.process_all_episodes()

    elif choice == '2':
        # Process limited number
        try:
            limit = int(input("Enter number of episodes to process: "))
            stats = processor.process_all_episodes(limit=limit)
        except ValueError:
            print("❌ Invalid number")
            return

    elif choice == '3':
        # Process single episode
        season = input("Enter season number: ").strip()
        episode = input("Enter episode number: ").strip()

        # Find matching episode
        metadata_files = processor.get_metadata_files()
        target_episode = None

        for metadata in metadata_files:
            if (str(metadata.get('season', '')) == season and
                    str(metadata.get('episode_number', '')) == episode):
                target_episode = metadata
                break

        if target_episode:
            success = processor.process_episode(target_episode)
            stats = {'total': 1, 'success': 1 if success else 0, 'failed': 0 if success else 1}
        else:
            print(f"❌ Episode {season}.{episode} not found")
            return

    else:
        print("❌ Invalid choice")
        return

    # Final summary
    print(f"\n🎯 Final Results:")
    print(f"Total episodes: {stats['total']}")
    print(f"Successfully processed: {stats['success']}")
    print(f"Failed: {stats['failed']}")

    if stats['success'] > 0:
        print(f"\n✅ Your Qdrant Cloud collection now contains searchable historical data!")
        print(f"🌐 Ready to test queries on your live platform:")
        print(f"https://historical-research-platform-320103070676.us-central1.run.app")


if __name__ == "__main__":
    main()