"""
Notification Endpoints for SalonAI Workforce Platform.
Provides APIs for fetching and marking notifications as read for logged-in users.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from infrastructure.db import get_db, User, Notification
from api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    is_read: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="Get User Notifications",
    description="Retrieve all notifications for the currently authenticated user."
)
def get_user_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch all notifications for the logged-in user."""
    logger.info(f"Fetching notifications for user {current_user.id}")
    
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_cleared == False
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    
    return [
        NotificationResponse(
            id=str(n.id),
            user_id=str(n.user_id),
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at.isoformat()
        )
        for n in notifications
    ]


@router.post(
    "/{notification_id}/read",
    summary="Mark Notification as Read",
    description="Mark a specific notification as read."
)
def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    try:
        notif_uuid = UUID(notification_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid notification ID format"
        )
        
    notification = (
        db.query(Notification)
        .filter(Notification.id == notif_uuid, Notification.user_id == current_user.id)
        .first()
    )
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
        
    notification.is_read = True
    notification.is_cleared = True
    db.commit()
    return {"success": True, "message": "Notification marked as read and cleared"}


@router.post(
    "/read-all",
    summary="Clear All Notifications",
    description="Marks all notifications for the currently logged-in user as cleared and read."
)
def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications for current user as cleared and read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).update(
        {Notification.is_cleared: True, Notification.is_read: True},
        synchronize_session=False
    )
    
    db.commit()
    return {"success": True, "message": "All notifications cleared successfully"}

