#!/usr/bin/env python3
"""
AWS Fleet Transcript Processor
Processes existing Google Drive transcripts to Qdrant Cloud
Optimized for t3.large spot instances
MODIFIED: Limited to 3 files for testing
"""

import os
import json
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Core libraries
from tqdm import tqdm

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


class AWSTranscriptProcessor:
    """Process existing transcripts for Qdrant upload on AWS"""

    def __init__(self):
        """Initialize processor for AWS environment"""

        logger.info("🚀 AWS Fleet Transcript Processor Starting")

        # Configuration from environment variables
        self.gcs_project = os.environ.get('GCS_PROJECT_ID', 'podcast-transcription-462218')
        self.gcs_bucket = os.environ.get('GCS_BUCKET_NAME', 'ai_knowledgebase')
        self.gcs_metadata_prefix = 'podcasts/revolutions/metadata/'

        # Qdrant Cloud configuration
        self.qdrant_url = os.environ['QDRANT_CLOUD_URL']
        self.qdrant_api_key = os.environ['QDRANT_CLOUD_API_KEY']
        self.collection_name = os.environ.get('QDRANT_COLLECTION_NAME', 'historical_sources')

        # OpenAI configuration
        self.openai_api_key = os.environ['OPENAI_API_KEY']

        # Google credentials (should be in AMI)
        self.credentials_path = '/home/ubuntu/credentials.json'  # Standard AMI location

        # Processing settings optimized for AWS - CONSERVATIVE
        self.chunk_size = 800  # Smaller chunks
        self.chunk_overlap = 150
        self.batch_size = 3  # Much smaller batches
        self.api_delay = 2.0  # Longer delays between API calls
        self.request_timeout = 60  # Timeout for requests

        # Revolution mapping
        self.revolution_mapping = {
            1: "English Civil War", 2: "American Revolution", 3: "French Revolution",
            4: "Haitian Revolution", 5: "Spanish American Wars of Independence",
            6: "July Revolution & Revolutions of 1830", 7: "German Revolution of 1848",
            8: "Paris Commune", 9: "Mexican Revolution", 10: "Russian Revolution"
        }

        self.historical_periods = {
            1: "1640-1660", 2: "1765-1783", 3: "1789-1799", 4: "1791-1804",
            5: "1808-1833", 6: "1830-1831", 7: "1848-1849", 8: "1871",
            9: "1910-1920", 10: "1917-1923"
        }

        # Initialize clients
        self._init_clients()

        # Track progress
        self.processed_count = 0
        self.total_chunks_created = 0
        self.start_time = time.time()

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

            # Test with a simple embedding
            test_response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input="test"
            )
            logger.info("✅ OpenAI client initialized and tested")

        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenAI client: {e}")
            raise

        # Qdrant client
        try:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=60  # Conservative timeout
            )

            # Test connection with timeout
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                logger.error(f"❌ Collection '{self.collection_name}' not found")
                logger.info(f"Available collections: {collection_names}")
                raise ValueError(f"Collection not found: {self.collection_name}")

            logger.info(f"✅ Qdrant connected - Collection: {self.collection_name}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Qdrant client: {e}")
            raise

    def get_all_metadata(self) -> List[Dict]:
        """Get all episode metadata from GCS"""

        logger.info("📂 Fetching all episode metadata from Google Cloud Storage...")

        try:
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            blobs = bucket.list_blobs(prefix=self.gcs_metadata_prefix)

            metadata_list = []

            for blob in blobs:
                if blob.name.endswith('.json'):
                    try:
                        content = blob.download_as_text()
                        metadata = json.loads(content)

                        # Validate required fields
                        if (metadata.get('google_doc_id') and
                                metadata.get('season') and
                                metadata.get('episode_number')):
                            metadata_list.append(metadata)
                        else:
                            logger.warning(f"⚠️ Skipping {blob.name}: missing required fields")

                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse {blob.name}: {e}")

            # Sort by season and episode - FIXED NUMERIC SORTING
            def sort_key(metadata):
                season = metadata.get('season', 0)
                episode_str = str(metadata.get('episode_number', '0'))

                # Handle episode numbers like "1", "1.1", "10.5" etc.
                try:
                    if '.' in episode_str:
                        parts = episode_str.split('.')
                        major = int(parts[0])
                        minor = int(parts[1]) if len(parts) > 1 else 0
                        episode_num = major + minor * 0.01  # 1.10 becomes 1.10, not 1.1
                    else:
                        episode_num = float(episode_str)
                except (ValueError, IndexError):
                    episode_num = 0

                return (season, episode_num)

            metadata_list.sort(key=sort_key)

            logger.info(f"📊 Found {len(metadata_list)} valid episodes to process")
            return metadata_list

        except Exception as e:
            logger.error(f"❌ Failed to fetch metadata: {e}")
            return []

    def get_google_doc_content(self, doc_id: str) -> Optional[str]:
        """Get transcript content from Google Doc"""

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

    def extract_transcript_text(self, full_content: str) -> str:
        """Extract just the transcript text, removing metadata header"""

        # Split on metadata delimiter
        parts = full_content.split('---')

        if len(parts) >= 3:
            # Content after second --- is the transcript
            transcript = '---'.join(parts[2:]).strip()
        else:
            # Fallback: use full content
            transcript = full_content

        return transcript

    def create_text_chunks(self, text: str, episode_metadata: Dict) -> List[Dict]:
        """Split text into semantic chunks - FIXED to prevent infinite loops"""

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

        # Multiple chunks with overlap - FIXED LOGIC
        start = 0
        chunk_index = 0
        max_chunks = 50  # Safety limit to prevent infinite loops

        while start < text_length and chunk_index < max_chunks:
            end = min(start + self.chunk_size, text_length)

            # Try to break at sentence boundary if not at end
            if end < text_length:
                # Look for sentence endings in the last 150 characters
                search_start = max(end - 150, start + self.chunk_size // 2)
                best_break = end

                for delimiter in ['. ', '! ', '? ', '\n\n']:
                    pos = text.rfind(delimiter, search_start, end)
                    if pos > search_start:
                        best_break = pos + len(delimiter)
                        break

                end = best_break

            chunk_text = text[start:end].strip()

            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_index,
                    'total_chunks': 0,  # Will update after all chunks created
                    'content_length': len(chunk_text),
                    **episode_metadata
                })
                chunk_index += 1

            # FIXED: Ensure forward progress
            new_start = end - self.chunk_overlap
            if new_start <= start:  # Prevent infinite loop
                new_start = start + self.chunk_size // 2  # Force progress

            start = new_start

            # Safety check
            if start >= text_length:
                break

        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total_chunks

        logger.info(f"📝 Created {total_chunks} chunks from {text_length} characters")
        return chunks

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a batch of texts - CONSERVATIVE"""

        logger.info(f"🔄 Creating embeddings for {len(texts)} texts...")

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
                timeout=30  # Conservative timeout
            )

            embeddings = [item.embedding for item in response.data]
            logger.info(f"✅ Created {len(embeddings)} embeddings")

            # Longer delay to respect rate limits
            time.sleep(self.api_delay)

            return embeddings

        except Exception as e:
            logger.error(f"❌ Failed to create embeddings batch: {e}")
            # Return empty embeddings on failure
            return [[0.0] * 1536] * len(texts)

    def upload_chunks_to_qdrant(self, chunks: List[Dict]) -> bool:
        """Upload chunks to Qdrant in batches"""

        if not chunks:
            return True

        try:
            # Process in batches
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]

                # Extract texts for embedding
                texts = [chunk['content'] for chunk in batch]

                # Create embeddings
                embeddings = self.create_embeddings_batch(texts)

                # Create Qdrant points
                points = []
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
                    # Generate unique point ID
                    point_id = int(time.time() * 1000000) + i + j

                    # Prepare payload (remove content to save space)
                    payload = {k: v for k, v in chunk.items() if k != 'content'}

                    points.append(
                        models.PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload=payload
                        )
                    )

                # Upload batch to Qdrant with logging
                logger.info(f"📤 Uploading batch of {len(points)} points to Qdrant...")
                self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"✅ Batch uploaded successfully")

                # Longer delay between batches
                time.sleep(self.api_delay * 3)

            logger.info(f"✅ Uploaded {len(chunks)} chunks to Qdrant")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to upload chunks: {e}")
            return False

    def prepare_episode_metadata(self, metadata: Dict) -> Dict:
        """Prepare metadata for each chunk"""

        # Ensure season is an integer for mapping lookup
        season = metadata.get('season', 0)
        if isinstance(season, str):
            try:
                season = int(season)
            except (ValueError, TypeError):
                season = 0

        return {
            # Source identification
            'source_type': 'podcast',
            'source_name': 'revolutions',

            # Episode details
            'season': season,
            'episode_number': metadata.get('episode_number', '0'),
            'episode_title': metadata.get('title', 'Unknown'),
            'revolution': self.revolution_mapping.get(season, 'Unknown Revolution'),
            'historical_period': self.historical_periods.get(season, 'Unknown'),
            'podcast_date': metadata.get('published', ''),

            # Document metadata
            'document_type': 'podcast_transcript',
            'authors': 'Mike Duncan',
            'publication_date': metadata.get('published', ''),
            'document_title': metadata.get('title', 'Unknown'),

            # Processing metadata
            'processed_date': datetime.now().isoformat(),
            'embedding_model': 'text-embedding-3-small',
            'processing_version': 'v2.0'
        }

    def process_single_episode(self, metadata: Dict) -> bool:
        """Process a single episode"""

        season = metadata.get('season', 0)
        episode_num = metadata.get('episode_number', '0')
        title = metadata.get('title', 'Unknown')
        episode_id = f"{season}.{episode_num}"

        logger.info(f"📻 Processing {episode_id}: {title}")

        try:
            # Get Google Doc content
            doc_id = metadata.get('google_doc_id')
            if not doc_id:
                logger.warning(f"⚠️ No Google Doc ID for {episode_id}")
                return False

            content = self.get_google_doc_content(doc_id)
            if not content:
                logger.warning(f"⚠️ Failed to get content for {episode_id}")
                return False

            # Extract transcript text
            transcript = self.extract_transcript_text(content)
            if not transcript or len(transcript) < 100:  # Minimum content check
                logger.warning(f"⚠️ Insufficient transcript content for {episode_id}")
                return False

            # Prepare episode metadata
            episode_metadata = self.prepare_episode_metadata(metadata)

            # Create chunks
            chunks = self.create_text_chunks(transcript, episode_metadata)
            if not chunks:
                logger.warning(f"⚠️ No chunks created for {episode_id}")
                return False

            # Upload to Qdrant
            success = self.upload_chunks_to_qdrant(chunks)

            if success:
                self.processed_count += 1
                self.total_chunks_created += len(chunks)
                logger.info(f"✅ {episode_id} complete - {len(chunks)} chunks uploaded")
                return True
            else:
                logger.error(f"❌ Failed to upload {episode_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error processing {episode_id}: {e}")
            return False

    def process_all_episodes(self) -> Dict[str, int]:
        """Process all episodes - LIMITED TO 3 FOR TESTING"""

        logger.info("🧪 Starting LIMITED episode processing (3 files max)")

        # Get all metadata
        all_metadata = self.get_all_metadata()
        if not all_metadata:
            logger.error("❌ No episodes found to process")
            return {'total': 0, 'success': 0, 'failed': 0}

        # LIMIT TO 3 FILES FOR FULL TEST
        all_metadata = all_metadata[:3]
        logger.info(f"🧪 FULL TEST: Processing {len(all_metadata)} files")

        # Process each episode
        stats = {'total': len(all_metadata), 'success': 0, 'failed': 0}

        for i, metadata in enumerate(all_metadata):
            try:
                logger.info(f"📊 Progress: {i + 1}/{len(all_metadata)}")

                if self.process_single_episode(metadata):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

            except Exception as e:
                logger.error(f"❌ Unexpected error processing episode {i + 1}: {e}")
                stats['failed'] += 1

        # Final summary
        total_time = time.time() - self.start_time
        logger.info(f"🎉 LIMITED Processing complete!")
        logger.info(f"⏱️ Total time: {total_time / 60:.1f} minutes")
        logger.info(f"📊 Episodes: {stats['success']}/{stats['total']} successful")
        logger.info(f"🔢 Total chunks created: {self.total_chunks_created}")

        return stats


def main():
    """Main processing function"""

    print("🏛️ AWS Fleet Transcript Processor")
    print("Processing Revolutions Podcast transcripts to Qdrant Cloud")
    print("🧪 FULL TEST MODE: Processing 3 files")
    print("=" * 60)

    # Environment check
    required_env = [
        'QDRANT_CLOUD_URL', 'QDRANT_CLOUD_API_KEY', 'OPENAI_API_KEY',
        'GCS_PROJECT_ID', 'GCS_BUCKET_NAME'
    ]

    missing_env = [var for var in required_env if not os.environ.get(var)]
    if missing_env:
        print(f"❌ Missing environment variables: {missing_env}")
        print("Set them before running this script")
        return

    try:
        # Initialize processor
        processor = AWSTranscriptProcessor()

        # Process limited episodes
        stats = processor.process_all_episodes()

        # Final results
        print(f"\n🎯 Final Results:")
        print(f"Total episodes: {stats['total']}")
        print(f"Successfully processed: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total chunks uploaded: {processor.total_chunks_created}")

        if stats['success'] > 0:
            print(f"\n✅ SUCCESS! 3-file test completed successfully!")
            print(f"🔢 Added {processor.total_chunks_created} new chunks to Qdrant Cloud")
            print(f"🌐 Ready to test queries on your platform")

    except Exception as e:
        print(f"❌ Processing failed: {e}")
        logger.exception("Full error details:")


if __name__ == "__main__":
    main()