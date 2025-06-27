#!/usr/bin/env python3
"""
AWS Fleet Transcript Processor - History of Rome Edition
Processes existing Google Drive transcripts to Qdrant Cloud
Optimized for t3.large spot instances
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


class AWSHistoryRomeProcessor:
    """Process existing History of Rome transcripts for Qdrant upload on AWS"""

    def __init__(self):
        """Initialize processor for AWS environment"""

        logger.info("🏛️ AWS Fleet History of Rome Processor Starting")

        # Configuration from environment variables
        self.gcs_project = os.environ.get('GCS_PROJECT_ID', 'podcast-transcription-462218')
        self.gcs_bucket = os.environ.get('GCS_BUCKET_NAME', 'ai_knowledgebase')
        self.gcs_metadata_prefix = 'podcasts/history_of_rome/metadata/'

        # Qdrant Cloud configuration
        self.qdrant_url = os.environ['QDRANT_CLOUD_URL']
        self.qdrant_api_key = os.environ['QDRANT_CLOUD_API_KEY']
        self.collection_name = os.environ.get('QDRANT_COLLECTION_NAME', 'historical_sources')

        # OpenAI configuration
        self.openai_api_key = os.environ['OPENAI_API_KEY']

        # Google credentials (should be in AMI)
        self.credentials_path = '/home/ubuntu/credentials.json'  # Standard AMI location

        # Processing settings optimized for AWS
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.api_delay = 0.1  # Small delay between API calls
        self.batch_size = 50  # Qdrant upload batch size

        # Initialize counters
        self.processed_count = 0
        self.total_chunks_created = 0
        self.start_time = time.time()

        # Initialize clients
        self._init_clients()

    def _init_clients(self):
        """Initialize Google Cloud and AI clients"""

        logger.info("🔧 Initializing clients...")

        try:
            # Google Cloud credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                        'https://www.googleapis.com/auth/cloud-platform']
            )

            # Initialize clients
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            self.gcs_client = storage.Client(credentials=self.credentials, project=self.gcs_project)

            # Qdrant client
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=60
            )

            # OpenAI client
            openai.api_key = self.openai_api_key

            logger.info("✅ All clients initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize clients: {e}")
            raise

    def get_historical_period(self, episode_number: int) -> str:
        """Get historical period based on episode number"""

        # Handle string episode numbers like "020a", "020b"
        if isinstance(episode_number, str):
            try:
                # Extract just the numeric part
                import re
                match = re.match(r'(\d+)', episode_number)
                if match:
                    episode_number = int(match.group(1))
                else:
                    episode_number = 0
            except:
                episode_number = 0

        # Use numeric ranges for period mapping
        if 1 <= episode_number <= 14:
            return "The Kings (753-509 BC)"
        elif 15 <= episode_number <= 24:
            return "Early Republic (509-264 BC)"
        elif 25 <= episode_number <= 34:
            return "Punic Wars (264-146 BC)"
        elif 35 <= episode_number <= 49:
            return "Late Republic Crisis (133-49 BC)"
        elif 50 <= episode_number <= 69:
            return "Caesar and Civil Wars (49-31 BC)"
        elif 70 <= episode_number <= 99:
            return "Early Empire (31 BC-96 AD)"
        elif 100 <= episode_number <= 129:
            return "High Empire (96-235 AD)"
        elif 130 <= episode_number <= 159:
            return "Crisis of Third Century (235-284 AD)"
        elif 160 <= episode_number <= 179:
            return "Late Empire (284-476 AD)"
        elif episode_number >= 180:
            return "Fall of Rome (476-550 AD)"
        else:
            return "Roman History"

    def get_all_metadata(self) -> List[Dict]:
        """Get all History of Rome episode metadata from GCS"""

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

                        # Validate required fields (same as Revolutions, but no season required)
                        if (metadata.get('google_doc_id') and
                                metadata.get('episode_number')):
                            metadata_list.append(metadata)
                        else:
                            logger.warning(f"⚠️ Skipping {blob.name}: missing required fields")

                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse {blob.name}: {e}")

            # Sort by episode number (string sort works for zero-padded: "001", "002", "003a", "003b")
            metadata_list.sort(key=lambda x: str(x.get('episode_number', '0')).zfill(10))

            logger.info(f"📊 Found {len(metadata_list)} valid episodes to process")
            return metadata_list

        except Exception as e:
            logger.error(f"❌ Failed to fetch metadata: {e}")
            return []

    def get_google_doc_content(self, doc_id: str) -> Optional[str]:
        """Fetch content from Google Doc"""

        try:
            time.sleep(self.api_delay)  # Rate limiting

            document = self.docs_service.documents().get(documentId=doc_id).execute()
            content = ""

            for element in document.get('body', {}).get('content', []):
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
        """Split text into semantic chunks"""

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

        # Multiple chunks with overlap
        start = 0
        chunk_index = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            # Try to break at sentence boundary if not at end
            if end < text_length:
                # Look for sentence endings in the overlap region
                search_start = max(end - self.chunk_overlap, start + self.chunk_size // 2)
                best_break = end

                for delimiter in ['. ', '! ', '? ', '\n\n']:
                    last_pos = text.rfind(delimiter, search_start, end)
                    if last_pos != -1:
                        best_break = last_pos + len(delimiter)
                        break

                end = best_break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_index,
                    'total_chunks': 0,  # Will be updated later
                    'content_length': len(chunk_text),
                    **episode_metadata
                })
                chunk_index += 1

            # Move start position
            start = max(end - self.chunk_overlap, start + 1)

        # Update total chunks count
        for chunk in chunks:
            chunk['total_chunks'] = len(chunks)

        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks"""

        try:
            time.sleep(self.api_delay)

            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )

            return [embedding.embedding for embedding in response.data]

        except Exception as e:
            logger.error(f"❌ Failed to generate embeddings: {e}")
            raise

    def upload_chunks_to_qdrant(self, chunks: List[Dict]) -> bool:
        """Upload chunks to Qdrant with embeddings"""

        try:
            # Extract texts for embedding
            texts = [chunk['content'] for chunk in chunks]

            # Generate embeddings
            embeddings = self.generate_embeddings(texts)

            # Prepare points for upload
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Generate deterministic UUID based on content for deduplication
                import uuid
                import hashlib

                # Create unique identifier from episode and chunk info
                unique_string = f"history_rome_{chunk['episode_number']}_{chunk['chunk_index']}_{chunk['source_name']}"

                # Generate deterministic UUID using namespace and unique string
                namespace = uuid.UUID('12345678-1234-5678-1234-123456789abc')
                point_id = str(uuid.uuid5(namespace, unique_string))

                points.append(models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=chunk
                ))

            # Upload to Qdrant (upsert will replace existing points with same ID)
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            # Small delay to avoid rate limits
            time.sleep(self.api_delay * 2)

            logger.info(f"✅ Upserted {len(chunks)} chunks to Qdrant (duplicates automatically replaced)")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to upload chunks: {e}")
            return False

    def prepare_episode_metadata(self, metadata: Dict) -> Dict:
        """Prepare metadata for each chunk"""

        episode_number = metadata.get('episode_number', '0')

        # Keep episode_number as string, but extract numeric part for historical period
        if isinstance(episode_number, str):
            try:
                import re
                match = re.match(r'(\d+)', episode_number)
                numeric_episode = int(match.group(1)) if match else 0
            except:
                numeric_episode = 0
        else:
            numeric_episode = int(episode_number) if episode_number else 0

        return {
            # Source identification
            'source_type': 'podcast',
            'source_name': 'history_of_rome',

            # Episode details (keep original format)
            'episode_number': episode_number,  # Keep as original string like "003a"
            'episode_title': metadata.get('title', 'Unknown'),
            'historical_period': self.get_historical_period(numeric_episode),  # Use numeric part
            'podcast_date': metadata.get('published', ''),

            # Processing metadata
            'processed_date': datetime.now().isoformat(),
            'embedding_model': 'text-embedding-3-small',
            'processing_version': 'v2.0',
            'google_doc_id': metadata.get('google_doc_id', ''),
            'google_doc_url': metadata.get('google_doc_url', '')
        }

    def ensure_qdrant_indexes(self):
        """Create necessary indexes for efficient querying"""

        logger.info("🔧 Ensuring Qdrant indexes exist...")

        try:
            # Create index for source_name field
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="source_name",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            logger.info("✅ Created index for source_name")

        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✅ source_name index already exists")
            else:
                logger.warning(f"⚠️ Could not create source_name index: {e}")

        try:
            # Create index for episode_number field
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="episode_number",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            logger.info("✅ Created index for episode_number")

        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✅ episode_number index already exists")
            else:
                logger.warning(f"⚠️ Could not create episode_number index: {e}")

    def find_duplicate_episodes(self) -> Dict[str, List]:
        """Find episodes that have multiple chunks (indicating duplicates)"""

        logger.info("🔍 Scanning for duplicate episodes in Qdrant...")

        # Ensure indexes exist first
        self.ensure_qdrant_indexes()

        try:
            # Get all points from the collection (without filtering first)
            all_points = []
            next_page_token = None

            logger.info("📥 Fetching all points from Qdrant...")

            while True:
                result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=next_page_token,
                    with_payload=True
                )

                points, next_page_token = result

                # Filter for History of Rome points locally
                rome_points = [
                    point for point in points
                    if point.payload and point.payload.get('source_name') == 'history_of_rome'
                ]

                all_points.extend(rome_points)
                logger.info(f"📊 Fetched {len(all_points)} History of Rome points so far...")

                if next_page_token is None:
                    break

            logger.info(f"📋 Total History of Rome points found: {len(all_points)}")

            if not all_points:
                logger.info("✅ No History of Rome points found - no duplicates possible!")
                return {}

            # Group by episode number and chunk index
            episode_chunks = {}
            for point in all_points:
                episode_num = point.payload.get('episode_number', 'unknown')
                chunk_index = point.payload.get('chunk_index', 0)

                key = f"{episode_num}_{chunk_index}"
                if key not in episode_chunks:
                    episode_chunks[key] = []
                episode_chunks[key].append(point.id)

            # Find duplicates
            duplicates = {k: v for k, v in episode_chunks.items() if len(v) > 1}

            if duplicates:
                logger.info(f"🚨 Found {len(duplicates)} chunk positions with duplicates:")
                total_duplicate_points = sum(len(v) - 1 for v in duplicates.values())  # -1 because we keep one
                logger.info(f"📊 Total duplicate points to remove: {total_duplicate_points}")

                for key, point_ids in list(duplicates.items())[:5]:  # Show first 5
                    episode, chunk = key.split('_')
                    logger.info(f"   Episode {episode}, Chunk {chunk}: {len(point_ids)} copies")

                if len(duplicates) > 5:
                    logger.info(f"   ... and {len(duplicates) - 5} more")
            else:
                logger.info("✅ No duplicates found!")

            return duplicates

        except Exception as e:
            logger.error(f"❌ Failed to scan for duplicates: {e}")
            return {}

    def clean_duplicate_episodes(self, episode_numbers: List[str] = None) -> bool:
        """Remove duplicate chunks for specified episodes (or all if None)"""

        if episode_numbers:
            logger.info(f"🧹 Cleaning duplicates for episodes: {episode_numbers}")
        else:
            logger.info("🧹 Cleaning ALL duplicate episodes...")

        try:
            # Find duplicates
            duplicates = self.find_duplicate_episodes()

            if not duplicates:
                logger.info("✅ No duplicates to clean!")
                return True

            # Filter by episode numbers if specified
            if episode_numbers:
                episode_set = set(str(ep) for ep in episode_numbers)
                duplicates = {
                    k: v for k, v in duplicates.items()
                    if k.split('_')[0] in episode_set
                }

            if not duplicates:
                logger.info(f"✅ No duplicates found for specified episodes: {episode_numbers}")
                return True

            # Remove duplicates (keep the first point, delete the rest)
            points_to_delete = []
            for key, point_ids in duplicates.items():
                # Keep the first point, mark the rest for deletion
                points_to_delete.extend(point_ids[1:])
                episode, chunk = key.split('_')
                logger.info(f"   Episode {episode}, Chunk {chunk}: keeping 1, deleting {len(point_ids) - 1}")

            # Delete in batches
            batch_size = 100
            total_deleted = 0

            for i in range(0, len(points_to_delete), batch_size):
                batch = points_to_delete[i:i + batch_size]

                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=batch)
                )

                total_deleted += len(batch)
                logger.info(f"🗑️ Deleted batch {i // batch_size + 1}: {len(batch)} points (total: {total_deleted})")

                # Small delay between batches
                time.sleep(0.5)

            logger.info(f"✅ Successfully deleted {total_deleted} duplicate points!")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to clean duplicates: {e}")
            return False

    def delete_all_podcast_data(self, podcast_name: str = "history_of_rome") -> bool:
        """Delete ALL data for a specific podcast"""

        logger.info(f"🗑️ DELETING ALL DATA for podcast: {podcast_name}")
        logger.info("⚠️ This action is IRREVERSIBLE!")

        # Ensure indexes exist
        self.ensure_qdrant_indexes()

        try:
            # Get all points for this podcast
            all_points = []
            next_page_token = None

            while True:
                try:
                    # Try filtered approach first
                    result = self.qdrant_client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="source_name",
                                    match=models.MatchValue(value=podcast_name)
                                )
                            ]
                        ),
                        limit=100,
                        offset=next_page_token,
                        with_payload=True
                    )

                except Exception as filter_error:
                    logger.warning(f"⚠️ Filtering failed, using local filtering: {filter_error}")

                    # Fallback: get all points and filter locally
                    result = self.qdrant_client.scroll(
                        collection_name=self.collection_name,
                        limit=100,
                        offset=next_page_token,
                        with_payload=True
                    )

                    points, next_page_token = result
                    # Filter locally
                    points = [
                        point for point in points
                        if point.payload and point.payload.get('source_name') == podcast_name
                    ]
                    result = (points, next_page_token)

                points, next_page_token = result
                all_points.extend(points)
                logger.info(f"📊 Found {len(all_points)} {podcast_name} points so far...")

                if next_page_token is None:
                    break

            if not all_points:
                logger.info(f"✅ No {podcast_name} data found to delete")
                return True

            logger.info(f"🚨 Found {len(all_points)} total points to delete for {podcast_name}")

            # Delete in batches
            batch_size = 100
            total_deleted = 0

            for i in range(0, len(all_points), batch_size):
                batch_points = all_points[i:i + batch_size]
                point_ids = [point.id for point in batch_points]

                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=point_ids)
                )

                total_deleted += len(point_ids)
                logger.info(f"🗑️ Deleted batch {i // batch_size + 1}: {len(point_ids)} points (total: {total_deleted})")

                # Small delay between batches
                time.sleep(0.5)

            logger.info(f"✅ Successfully deleted ALL {total_deleted} points for {podcast_name}!")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete {podcast_name} data: {e}")
            return False

    def delete_episode_completely(self, episode_numbers: List[str]) -> bool:
        """Completely remove all chunks for specified episodes"""

        logger.info(f"🗑️ Completely deleting episodes: {episode_numbers}")

        # Ensure indexes exist
        self.ensure_qdrant_indexes()

        try:
            for episode_num in episode_numbers:
                # Find all points for this episode
                result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_name",
                                match=models.MatchValue(value="history_of_rome")
                            ),
                            models.FieldCondition(
                                key="episode_number",
                                match=models.MatchValue(value=episode_num)
                            )
                        ]
                    ),
                    limit=1000,  # Should be enough for one episode
                    with_payload=True
                )

                points, _ = result

                if points:
                    point_ids = [point.id for point in points]

                    self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.PointIdsList(points=point_ids)
                    )

                    logger.info(f"🗑️ Deleted {len(point_ids)} chunks for episode {episode_num}")
                else:
                    logger.info(f"⚠️ No chunks found for episode {episode_num}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete episodes: {e}")
            return False

    def check_episode_already_processed(self, episode_number: str) -> bool:
        """Check if episode chunks already exist in Qdrant"""

        try:
            # Ensure indexes exist
            self.ensure_qdrant_indexes()

            # Search for any chunks from this episode
            search_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_name",
                            match=models.MatchValue(value="history_of_rome")
                        ),
                        models.FieldCondition(
                            key="episode_number",
                            match=models.MatchValue(value=episode_number)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )

            return len(search_result[0]) > 0

        except Exception as e:
            logger.warning(f"⚠️ Could not check if episode {episode_number} exists (will reprocess): {e}")
            return False

    def process_single_episode(self, metadata: Dict, force_reprocess: bool = False) -> bool:
        """Process a single episode"""

        episode_num = metadata.get('episode_number', '0')
        title = metadata.get('title', 'Unknown')
        episode_id = f"rome_{episode_num}"

        logger.info(f"🏛️ Processing {episode_id}: {title}")

        # Check if already processed (unless forced)
        if not force_reprocess and self.check_episode_already_processed(str(episode_num)):
            logger.info(f"⏭️ Episode {episode_id} already processed, skipping (use force_reprocess=True to override)")
            self.processed_count += 1
            return True

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

    def process_all_episodes(self, force_reprocess: bool = False) -> Dict[str, int]:
        """Process all episodes"""

        logger.info("🚀 Starting full History of Rome episode processing")

        # Get all metadata
        all_metadata = self.get_all_metadata()
        if not all_metadata:
            logger.error("❌ No episodes found to process")
            return {'total': 0, 'success': 0, 'failed': 0}

        # Process each episode
        stats = {'total': len(all_metadata), 'success': 0, 'failed': 0}

        for i, metadata in enumerate(all_metadata):
            try:
                logger.info(f"📊 Progress: {i + 1}/{len(all_metadata)}")

                if self.process_single_episode(metadata, force_reprocess):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

                # Progress update every 10 episodes
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - self.start_time
                    rate = (i + 1) / elapsed * 60  # episodes per minute
                    remaining = (len(all_metadata) - i - 1) / rate if rate > 0 else 0

                    logger.info(f"📈 Progress: {i + 1}/{len(all_metadata)} episodes")
                    logger.info(f"⏱️ Rate: {rate:.1f} episodes/min, ETA: {remaining:.1f} min")
                    logger.info(f"📊 Success: {stats['success']}, Failed: {stats['failed']}")
                    logger.info(f"🔢 Total chunks created: {self.total_chunks_created}")

            except Exception as e:
                logger.error(f"❌ Unexpected error processing episode {i + 1}: {e}")
                stats['failed'] += 1

        # Final summary
        total_time = time.time() - self.start_time
        logger.info(f"🎉 Processing complete!")
        logger.info(f"⏱️ Total time: {total_time / 60:.1f} minutes")
        logger.info(f"📊 Episodes: {stats['success']}/{stats['total']} successful")
        logger.info(f"🔢 Total chunks created: {self.total_chunks_created}")
        logger.info(f"📈 Average rate: {stats['total'] / (total_time / 60):.1f} episodes/minute")

        return stats


def main():
    """Main processing function"""

    print("🏛️ AWS Fleet History of Rome Processor")
    print("Processing History of Rome Podcast transcripts to Qdrant Cloud")
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

    # Parse command line arguments
    import sys
    args = sys.argv[1:]

    # Check for cleanup operations
    if '--episode' in args:
        # Find episode number after --episode
        try:
            episode_index = args.index('--episode')
            if episode_index + 1 < len(args):
                target_episode = args[episode_index + 1]
                print(f"🎯 SINGLE EPISODE MODE: Processing episode {target_episode}")

                processor = AWSHistoryRomeProcessor()

                # Get all metadata to find the target episode
                all_metadata = processor.get_all_metadata()
                target_metadata = None

                for metadata in all_metadata:
                    if str(metadata.get('episode_number', '')).strip() == target_episode.strip():
                        target_metadata = metadata
                        break

                if target_metadata:
                    print(f"📄 Found: {target_metadata.get('title', 'Unknown Title')}")

                    # Force reprocess for single episode
                    success = processor.process_single_episode(target_metadata, force_reprocess=True)

                    if success:
                        print(f"✅ Episode {target_episode} processed successfully!")
                    else:
                        print(f"❌ Failed to process episode {target_episode}")
                else:
                    print(f"❌ Episode {target_episode} not found in metadata")
                    print("Available episodes:")
                    for metadata in all_metadata[:10]:  # Show first 10
                        ep_num = metadata.get('episode_number', 'unknown')
                        title = metadata.get('title', 'Unknown')[:50]
                        print(f"   {ep_num}: {title}")
                    if len(all_metadata) > 10:
                        print(f"   ... and {len(all_metadata) - 10} more")

                return
            else:
                print("❌ Please specify episode number after --episode")
                print("   Example: python3 script.py --episode 003a")
                return
        except ValueError:
            print("❌ Invalid --episode usage")
            return

    if '--scan-duplicates' in args:
        print("🔍 SCAN MODE: Looking for duplicate episodes...")
        processor = AWSHistoryRomeProcessor()
        duplicates = processor.find_duplicate_episodes()
        if duplicates:
            print(f"\n💡 To clean duplicates, run:")
            print(f"   python3 {sys.argv[0]} --clean-duplicates")
        return

    if '--clean-duplicates' in args:
        print("🧹 CLEANUP MODE: Removing duplicate episodes...")
        processor = AWSHistoryRomeProcessor()
        success = processor.clean_duplicate_episodes()
        if success:
            print("✅ Duplicate cleanup complete!")
        return

    if '--delete-all-rome' in args:
        print("🗑️ DELETE ALL MODE: Removing ALL History of Rome data...")
        print("⚠️ This will delete EVERYTHING for History of Rome podcast!")

        # Safety confirmation
        confirm = input("Type 'DELETE ALL ROME' to confirm: ")
        if confirm != "DELETE ALL ROME":
            print("❌ Deletion cancelled - confirmation text did not match")
            return

        processor = AWSHistoryRomeProcessor()
        success = processor.delete_all_podcast_data("history_of_rome")
        if success:
            print("✅ All History of Rome data deleted!")
        return

    if '--delete-podcast' in args:
        # Find podcast name after --delete-podcast
        try:
            delete_index = args.index('--delete-podcast')
            if delete_index + 1 < len(args):
                podcast_name = args[delete_index + 1]
                print(f"🗑️ DELETE PODCAST MODE: Removing ALL data for: {podcast_name}")
                print(f"⚠️ This will delete EVERYTHING for {podcast_name}!")

                # Safety confirmation
                confirm = input(f"Type 'DELETE {podcast_name.upper()}' to confirm: ")
                if confirm != f"DELETE {podcast_name.upper()}":
                    print("❌ Deletion cancelled - confirmation text did not match")
                    return

                processor = AWSHistoryRomeProcessor()
                success = processor.delete_all_podcast_data(podcast_name)
                if success:
                    print(f"✅ All {podcast_name} data deleted!")
                return
            else:
                print("❌ Please specify podcast name after --delete-podcast")
                print("   Example: python3 script.py --delete-podcast history_of_rome")
                return
        except ValueError:
            print("❌ Invalid --delete-podcast usage")
            return

    if '--delete-episodes' in args:
        # Find episode numbers after --delete-episodes
        try:
            delete_index = args.index('--delete-episodes')
            episode_numbers = []
            for i in range(delete_index + 1, len(args)):
                if args[i].startswith('--'):
                    break
                episode_numbers.append(args[i])

            if not episode_numbers:
                print("❌ Please specify episode numbers to delete")
                print("   Example: python3 script.py --delete-episodes 001 002 003a")
                return

            print(f"🗑️ DELETE MODE: Removing episodes {episode_numbers}")
            processor = AWSHistoryRomeProcessor()
            success = processor.delete_episode_completely(episode_numbers)
            if success:
                print("✅ Episode deletion complete!")
            return

        except ValueError:
            print("❌ Invalid --delete-episodes usage")
            return

    # Check for force reprocess flag
    force_reprocess = '--force' in args or '--reprocess' in args

    if force_reprocess:
        print("🔄 FORCE REPROCESS MODE: Will overwrite existing episodes in Qdrant")
    else:
        print("📋 NORMAL MODE: Will skip episodes already processed")
        print("\n💡 Available options:")
        print("   --episode 003a                 : Process single episode")
        print("   --scan-duplicates              : Check for duplicate episodes")
        print("   --clean-duplicates             : Remove duplicate episodes")
        print("   --delete-episodes 001 002      : Delete specific episodes")
        print("   --delete-all-rome              : Delete ALL History of Rome data")
        print("   --delete-podcast history_of_rome: Delete ALL data for any podcast")
        print("   --force                        : Reprocess all episodes")

    try:
        # Initialize processor
        processor = AWSHistoryRomeProcessor()

        # Process all episodes
        stats = processor.process_all_episodes(force_reprocess=force_reprocess)

        # Final results
        print(f"\n🎯 Final Results:")
        print(f"Total episodes: {stats['total']}")
        print(f"Successfully processed: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total chunks uploaded: {processor.total_chunks_created}")

        if stats['success'] > 0:
            print(f"\n✅ SUCCESS! Your Qdrant Cloud collection now contains searchable Roman historical data!")
            print(f"🌐 Ready to test advanced queries on your platform:")
            print(f"https://historical-research-platform-320103070676.us-central1.run.app")

            # Estimate collection size
            avg_chunks = processor.total_chunks_created / stats['success'] if stats['success'] > 0 else 0
            print(f"📊 Collection now contains ~{processor.total_chunks_created:,} searchable text chunks")
            print(f"📈 Average {avg_chunks:.1f} chunks per episode")

    except Exception as e:
        print(f"❌ Processing failed: {e}")
        logger.exception("Full error details:")


if __name__ == "__main__":
    main()