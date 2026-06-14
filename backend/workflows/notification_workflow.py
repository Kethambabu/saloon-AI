"""
Notification Workflows — Orchestrating user notifications dispatch and updates.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional
from db.database import SessionLocal
from db.models import User, Notification

logger = logging.getLogger(__name__)


def create_notification_workflow(
    user_id: Any,
    title: str,
    message: str,
) -> Dict[str, Any]:
    """
    Workflow to dispatch a notification to a specific user.
    """
    logger.info("[Workflow] Starting create_notification_workflow for user=%s, title=%s", user_id, title)
    
    session = SessionLocal()
    try:
        # Resolve user_id if passed as email or name
        from sqlalchemy import or_
        from db.models import User
        
        user_uuid = None
        try:
            user_uuid = uuid.UUID(str(user_id))
            user = session.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            user = session.query(User).filter(
                or_(
                    User.email == str(user_id),
                    User.username == str(user_id)
                )
            ).first()
            if user:
                user_uuid = user.id

        if not user_uuid:
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
            from db.models import User
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
