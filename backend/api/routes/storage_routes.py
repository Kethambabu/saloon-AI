"""
FastAPI router for Supabase Storage endpoints.
Allows authenticated users to upload files to profile-images, documents, or salon-assets buckets.
"""

import logging
import uuid
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException, status

from api.deps import get_current_user
from db.models import User
from utils.storage import upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storage", tags=["Storage"])

# Whitelist allowed buckets
ALLOWED_CATEGORIES = {
    "profile-images": "profile-images",
    "documents": "documents",
    "salon-assets": "salon-assets"
}


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload media assets to Supabase Storage",
    description="Upload profile images, documents, or salon assets. File size is restricted to 10MB."
)
async def upload_asset(
    category: str = Query(..., description="Target bucket category ('profile-images', 'documents', 'salon-assets')"),
    file: UploadFile = File(..., description="The multipart file to upload"),
    current_user: User = Depends(get_current_user)
):
    """Securely upload a file to Supabase Storage."""
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid storage category. Must be one of: {', '.join(ALLOWED_CATEGORIES.keys())}"
        )
        
    # Read file and limit to 10MB
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    try:
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds the maximum limit of 10MB."
            )
            
        # Generate a unique path inside the bucket
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "bin"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        target_path = f"uploads/{current_user.id}/{unique_filename}"
        
        # Determine content type
        content_type = file.content_type or "application/octet-stream"
        
        # Upload using the storage utility
        public_url = upload_file(
            bucket=category,
            file_path=target_path,
            file_bytes=content,
            content_type=content_type
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "unique_filename": unique_filename,
            "category": category,
            "public_url": public_url,
            "size_bytes": file_size,
            "content_type": content_type
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in storage upload endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload asset: {str(e)}"
        )
