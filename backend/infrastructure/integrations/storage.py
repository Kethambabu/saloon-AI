"""
Supabase Storage Utility Layer for SalonAI Workforce Platform.
Supports profile images, salon documents, and media asset uploads/downloads.
Uses administrative service role key to bypass client RLS policies for backend processing.
"""

import logging
from typing import Optional
from supabase import create_client, Client
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Helper to lazily initialize and cache the Supabase Client."""
    global _supabase_client
    if _supabase_client is None:
        url = settings.supabase_url
        # Use service role key if available for administrative actions, else fallback to anon key
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        
        if not url or not key:
            raise ValueError("Supabase configuration is incomplete! Verify SUPABASE_URL and key settings.")
            
        logger.info(f"Initializing Supabase client with URL: {url}")
        _supabase_client = create_client(url, key)
    return _supabase_client


def upload_file(bucket: str, file_path: str, file_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """
    Upload file bytes to a specified Supabase storage bucket.
    
    Args:
        bucket: Name of the bucket (e.g. 'profile-images', 'documents', 'salon-assets')
        file_path: Target path inside the bucket (e.g. 'users/123/avatar.jpg')
        file_bytes: Raw file contents
        content_type: MIME type of the file
        
    Returns:
        The public URL to the uploaded asset.
    """
    client = get_supabase_client()
    try:
        logger.info(f"Uploading file to bucket '{bucket}': {file_path}")
        
        # Ensure bucket exists or run upload
        # Supabase Python SDK upload method: client.storage.from_(bucket).upload(path, file, file_options)
        response = client.storage.from_(bucket).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Get public URL
        public_url = client.storage.from_(bucket).get_public_url(file_path)
        logger.info(f"Upload successful. Public URL: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Failed to upload file to Supabase: {str(e)}", exc_info=True)
        raise e


def download_file(bucket: str, file_path: str) -> bytes:
    """
    Download a file from a specified Supabase storage bucket.
    
    Args:
        bucket: Name of the bucket
        file_path: Path to the file inside the bucket
        
    Returns:
        Raw bytes of the downloaded file.
    """
    client = get_supabase_client()
    try:
        logger.info(f"Downloading file from bucket '{bucket}': {file_path}")
        return client.storage.from_(bucket).download(file_path)
    except Exception as e:
        logger.error(f"Failed to download file from Supabase: {str(e)}", exc_info=True)
        raise e


def delete_file(bucket: str, file_path: str) -> bool:
    """
    Delete a file from a specified Supabase storage bucket.
    
    Args:
        bucket: Name of the bucket
        file_path: Path to the file to delete
        
    Returns:
        True if successfully deleted, False otherwise.
    """
    client = get_supabase_client()
    try:
        logger.info(f"Deleting file from bucket '{bucket}': {file_path}")
        client.storage.from_(bucket).remove([file_path])
        return True
    except Exception as e:
        logger.warning(f"Failed to delete file from Supabase: {str(e)}")
        return False

