#!/usr/bin/env python3
"""
Memory-Optimized Data Processor: Revolutions Podcast to Qdrant Cloud
Processes episodes one at a time to avoid memory issues
"""

import os
import json
import gc
import time
from typing import List, Dict, Optional
from datetime import datetime
import logging

# Core libraries
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


class MemoryOptimizedProcessor:
    """Memory-optimized processor for large datasets"""

    def __init__(self):
        """Initialize with memory management"""

        logger.info("🚀 Initializing Memory-Optimized Data Processor")

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
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        # Memory-optimized settings
        self.chunk_size = 800  # Smaller chunks to reduce memory
        self.chunk_overlap = 100
        self.batch_size = 5  # Process 5 chunks at a time
        self.sleep_between_batches = 1  # 1 second pause

        # Revolution mapping
        self.revolution_mapping = {
            1: "English Civil War", 2: "American Revolution", 3: "French Revolution",
            4: "Haitian Revolution", 5: "Spanish American Wars of Independence",
            6: "July Revolution & Revolutions of 1830", 7: "German Revolution of 1848",
            8: "Paris Commune", 9: "Mexican Revolution", 10: "Russian Revolution"
        }

        # Initialize clients
        self._init_clients()

        # Track processed episodes to avoid duplicates
        self.processed_episodes = set()

    def _init_clients(self):
        """Initialize API clients with error handling"""

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
                timeout=120,  # Increased timeout
                check_compatibility=False
            )

            # Test connection
            collections = self.qdrant_client.get_collections()
            logger.info(f"✅ Qdrant client initialized: {len(collections.collections)} collections")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Qdrant client: {e}")
            raise

    def get_metadata_files(self, limit: Optional[int] = None) -> List[Dict]:
        """Get metadata files with memory management"""

        logger.info("📂 Fetching metadata files from Google Cloud Storage...")

        try:
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            blobs = bucket.list_blobs(prefix=self.gcs_metadata_prefix)

            metadata_files = []
            count = 0

            for blob in blobs:
                if blob.name.endswith('.json'):
                    if limit and count >= limit:
                        break

                    try:
                        content = blob.download_as_text()
                        metadata = json.loads(content)

                        # Only include if has required fields
                        if metadata.get('google_doc_id') and metadata.get('season') and metadata.get('episode_number'):
                            metadata['gcs_path'] = blob.name
                            metadata_files.append(metadata)
                            count += 1

                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse {blob.name}: {e}")

            logger.info(f"📊 Found {len(metadata_files)} valid metadata files")
            return metadata_files

        except Exception as e:
            logger.error(f"❌ Failed to fetch metadata files: {e}")
            return []

    def get_google_doc_content(self, doc_id: str) -> Optional[str]:
        """Retrieve content from Google Doc with memory cleanup"""

        try:
            doc = self.docs_service.documents().get(documentId=doc_id).execute()

            content = ""
            for element in doc.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    paragraph = element['paragraph']
                    for text_element in paragraph.get('elements', []):
                        if 'textRun' in text_element:
                            content += text_element['textRun']['content']

            # Clean up doc object from memory
            del doc
            gc.collect()

            return content.strip()

        except Exception as e:
            logger.error(f"❌ Failed to fetch Google Doc {doc_id}: {e}")
            return None

    def extract_transcript_content(self, full_content: str) -> str:
        """Extract transcript content efficiently"""

        # Remove metadata header
        parts = full_content.split('---')
        if len(parts) >= 3:
            transcript = '---'.join(parts[2:]).strip()
        else:
            transcript = full_content

        # Clean up parts list
        del parts

        return transcript

    def chunk_text_efficiently(self, text: str, episode_metadata: Dict) -> List[Dict]:
        """Create chunks with memory efficiency"""

        chunks = []
        text_length = len(text)

        if text_length <= self.chunk_size:
            # Single chunk
            return [{
                'content': text,
                'chunk_index': 0,
                'total_chunks': 1,
                'content_length': text_length,
                **episode_metadata
            }]

        # Multiple chunks
        chunk_count = 0
        start = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Try to break at sentence boundary
            if end < text_length:
                search_start = max(end - self.chunk_overlap, start + self.chunk_size // 2)

                for sentence_char in ['. ', '! ', '? ']:
                    pos = text.rfind(sentence_char, search_start, end)
                    if pos > 0:
                        end = pos + len(sentence_char)
                        break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_count,
                    'total_chunks': 0,  # Will update later
                    'content_length': len(chunk_text),
                    **episode_metadata
                })
                chunk_count += 1

            start = end - self.chunk_overlap

        # Update total_chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total_chunks

        return chunks

    def create_embedding_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Create embeddings in batches to manage memory"""

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )

            embeddings = [item.embedding for item in response.data]

            # Clean up response object
            del response
            gc.collect()

            return embeddings

        except Exception as e:
            logger.error(f"❌ Failed to create embeddings: {e}")
            return [None] * len(texts)

    def upload_chunks_to_qdrant(self, chunks: List[Dict]) -> bool:
        """Upload chunks in batches to manage memory"""

        if not chunks:
            return True

        try:
            # Process in batches
            total_uploaded = 0

            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]

                # Extract content for embeddings
                texts = [chunk['content'] for chunk in batch]

                # Create embeddings
                embeddings = self.create_embedding_batch(texts)

                # Create points
                points = []
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    if embedding is None:
                        continue

                    # Create unique point ID
                    point_id = int(time.time() * 1000000) + total_uploaded + j

                    # Prepare payload (remove content)
                    payload = {k: v for k, v in chunk.items() if k != 'content'}

                    points.append(
                        models.PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload=payload
                        )
                    )

                # Upload batch
                if points:
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                    total_uploaded += len(points)

                # Clean up batch data
                del texts, embeddings, points, batch
                gc.collect()

                # Pause between batches
                time.sleep(self.sleep_between_batches)

            logger.info(f"✅ Uploaded {total_uploaded} chunks to Qdrant")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to upload to Qdrant: {e}")
            return False

    def prepare_episode_metadata(self, metadata: Dict) -> Dict:
        """Prepare episode metadata"""

        season = metadata.get('season', 0)

        return {
            'source_type': 'podcast',
            'source_name': 'revolutions',
            'season': season,
            'episode_number': metadata.get('episode_number', '0'),
            'episode_title': metadata.get('title', 'Unknown'),
            'revolution': self.revolution_mapping.get(season, 'Unknown Revolution'),
            'historical_period': self._get_historical_period(season),
            'podcast_date': metadata.get('published', ''),
            'processed_date': datetime.now().isoformat(),
            'embedding_model': 'text-embedding-3-small',
            'processing_version': 'v2.0',
            'google_doc_id': metadata.get('google_doc_id', ''),
            'google_doc_url': metadata.get('google_doc_url', '')
        }

    def _get_historical_period(self, season: int) -> str:
        """Get historical period for season"""
        periods = {
            1: "1640-1660", 2: "1765-1783", 3: "1789-1799", 4: "1791-1804",
            5: "1808-1833", 6: "1830-1831", 7: "1848-1849", 8: "1871",
            9: "1910-1920", 10: "1917-1923"
        }
        return periods.get(season, "Unknown")

    def process_episode(self, metadata: Dict) -> bool:
        """Process single episode with memory management"""

        episode_id = f"{metadata.get('season', 0)}.{metadata.get('episode_number', '0')}"
        title = metadata.get('title', 'Unknown')

        # Check if already processed
        if episode_id in self.processed_episodes:
            logger.info(f"⏭️ Skipping already processed episode {episode_id}")
            return True

        logger.info(f"📻 Processing episode {episode_id}: {title}")

        try:
            # Get Google Doc content
            doc_id = metadata.get('google_doc_id')
            if not doc_id:
                logger.warning(f"⚠️ No Google Doc ID for episode {episode_id}")
                return False

            content = self.get_google_doc_content(doc_id)
            if not content:
                logger.warning(f"⚠️ Failed to get content for episode {episode_id}")
                return False

            # Extract transcript
            transcript = self.extract_transcript_content(content)
            del content  # Free memory

            if not transcript:
                logger.warning(f"⚠️ No transcript content for episode {episode_id}")
                return False

            # Prepare metadata
            episode_metadata = self.prepare_episode_metadata(metadata)

            # Create chunks
            chunks = self.chunk_text_efficiently(transcript, episode_metadata)
            del transcript  # Free memory

            if not chunks:
                logger.warning(f"⚠️ No chunks created for episode {episode_id}")
                return False

            # Upload to Qdrant
            success = self.upload_chunks_to_qdrant(chunks)
            del chunks  # Free memory

            # Force garbage collection
            gc.collect()

            if success:
                self.processed_episodes.add(episode_id)
                logger.info(f"✅ Episode {episode_id} processed successfully")
                return True
            else:
                logger.error(f"❌ Failed to upload episode {episode_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error processing episode {episode_id}: {e}")
            return False

    def process_episodes_safely(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Process episodes with memory management"""

        logger.info("🚀 Starting memory-optimized processing")

        # Get metadata files
        metadata_files = self.get_metadata_files(limit=limit)

        if not metadata_files:
            logger.error("❌ No metadata files found")
            return {'total': 0, 'success': 0, 'failed': 0}

        # Sort episodes
        metadata_files.sort(key=lambda x: (x.get('season', 0), x.get('episode_number', '0')))

        # Process one at a time
        stats = {'total': len(metadata_files), 'success': 0, 'failed': 0}

        for i, metadata in enumerate(metadata_files):
            logger.info(f"📊 Progress: {i + 1}/{len(metadata_files)}")

            try:
                if self.process_episode(metadata):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

                # Force garbage collection after each episode
                gc.collect()

                # Pause between episodes to prevent overwhelming APIs
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                stats['failed'] += 1

        logger.info(f"🎉 Processing complete!")
        logger.info(f"📊 Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")

        return stats


def main():
    """Main function with memory monitoring"""

    print("🏛️ Memory-Optimized Historical Research Platform Data Processor")
    print("=" * 60)

    try:
        processor = MemoryOptimizedProcessor()
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return

    # Get processing limit
    try:
        limit_input = input("Enter number of episodes to process (or 'all'): ").strip()
        limit = None if limit_input.lower() == 'all' else int(limit_input)
    except ValueError:
        print("❌ Invalid input, defaulting to 3 episodes")
        limit = 3

    # Process episodes
    stats = processor.process_episodes_safely(limit=limit)

    # Results
    print(f"\n🎯 Final Results:")
    print(f"Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")

    if stats['success'] > 0:
        print(f"\n✅ Success! Your platform now has searchable data!")
        print(f"🌐 Test it at: https://historical-research-platform-320103070676.us-central1.run.app")


if __name__ == "__main__":
    main()