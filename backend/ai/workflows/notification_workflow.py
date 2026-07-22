"""
Notification Workflows — Orchestrating user notifications dispatch and updates.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional
from infrastructure.db.database import SessionLocal
from infrastructure.db.models import User, Notification

logger = logging.getLogger(__name__)


def create_notification_workflow(
    user_id: Any,
    title: str,
    message: str,
    **kwargs,  # Accept extra kwargs (notification_type, tenant_id) gracefully without TypeError
) -> Dict[str, Any]:
    """
    Workflow to dispatch a notification to a specific user.
    user_id may be a User.id UUID, a Customer.id UUID (linked via User.customer_id),
    a User email address, or a username.
    """
    logger.info("[Workflow] Starting create_notification_workflow for user=%s, title=%s", user_id, title)
    
    session = SessionLocal()
    try:
        from sqlalchemy import or_
        from infrastructure.db.models import User
        
        user_uuid = None
        user = None
        try:
            user_uuid = uuid.UUID(str(user_id))
            # Try direct User.id lookup first
            user = session.query(User).filter(User.id == user_uuid).first()
            # If not found by User.id, try Customer.id → User.customer_id (fixes customer_id vs user_id mismatch)
            if user is None:
                user = session.query(User).filter(User.customer_id == user_uuid).first()
            if user:
                user_uuid = user.id
        except ValueError:
            # Non-UUID input: try email or username
            user = session.query(User).filter(
                or_(
                    User.email == str(user_id),
                    User.username == str(user_id)
                )
            ).first()
            if user:
                user_uuid = user.id

        if not user or not user_uuid:
            logger.warning("[Workflow] create_notification_workflow: User not found for identifier '%s'. Skipping.", user_id)
            return {"success": False, "error": f"User not found for identifier '{user_id}'"}

        notif = Notification(
            id=uuid.uuid4(),
            user_id=user_uuid,
            title=title,
            message=message,
            is_read=False
        )
        session.add(notif)
        session.commit()
        
        logger.info("[Workflow] create_notification_workflow completed successfully: notif_id=%s", notif.id)
        return {
            "success": True,
            "notification_id": str(notif.id),
            "user_id": str(user_uuid),
            "title": title,
            "message": message,
        }
    except Exception as exc:
        logger.error("[Workflow] Error in create_notification_workflow: %s", exc, exc_info=True)
        session.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        session.close()



def clear_user_notifications_workflow(
    user_id: Any,
) -> Dict[str, Any]:
    """
    Workflow to clear all active notifications for a specific user.
    """
    logger.info("[Workflow] Starting clear_user_notifications_workflow for user=%s", user_id)
    
    session = SessionLocal()
    try:
        user_uuid = None
        try:
            user_uuid = uuid.UUID(str(user_id))
            user = session.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            from infrastructure.db.models import User
            user = session.query(User).filter(User.email == str(user_id)).first()
            if user:
                user_uuid = user.id

        if not user_uuid:
            return {"success": False, "error": f"User not found for identifier '{user_id}'"}

        # Bulk update is_cleared and is_read status
        updated = session.query(Notification).filter(
            Notification.user_id == user_uuid
        ).update(
            {Notification.is_cleared: True, Notification.is_read: True},
            synchronize_session=False
        )
        session.commit()
        
        logger.info("[Workflow] clear_user_notifications_workflow completed successfully: cleared_count=%d", updated)
        return {
            "success": True,
            "cleared_count": updated,
            "user_id": str(user_uuid),
        }
    except Exception as exc:
        logger.error("[Workflow] Error in clear_user_notifications_workflow: %s", exc, exc_info=True)
        session.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        session.close()

