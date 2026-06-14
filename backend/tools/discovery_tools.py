"""
Booking Discovery Tools for SalonAI Workforce Platform.
Provides AI agent tools for discovering available branches, services, staff, and customers
before making bookings. Prevents hallucination and ensures entity existence.
"""

import logging
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from db.database import SessionLocal
from utils.entity_resolver import (
    list_branches as resolver_list_branches,
    list_services as resolver_list_services,
    list_staff as resolver_list_staff,
    search_customers as resolver_search_customers,
)

logger = logging.getLogger(__name__)


def list_available_branches() -> str:
    """
    Returns a list of all active salon branches with their details.
    Use this before suggesting a specific branch to a customer.
    
    Returns:
        JSON-formatted list of branches with id, name, code, city, address, phone
    """
    db = SessionLocal()
    try:
        branches = resolver_list_branches(db, active_only=True)
        logger.info(f"Listed {len(branches)} branches")
        
        if not branches:
            return "{\n  \"success\": true,\n  \"branches\": [],\n  \"message\": \"No active branches found in the system.\"\n}"
        
        # Format as readable text for agent
        formatted = "Available Branches:\n\n"
        for branch in branches:
            formatted += f"• {branch['name']} ({branch['code']})\n"
            formatted += f"  Location: {branch['address']}, {branch['city']}\n"
            formatted += f"  Phone: {branch['phone']}\n"
            formatted += f"  ID: {branch['id']}\n\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Error listing branches: {str(e)}", exc_info=True)
        return f"{{\n  \"success\": false,\n  \"error\": \"Failed to list branches: {str(e)}\"\n}}"
    finally:
        db.close()


def list_available_services() -> str:
    """
    Returns a list of all active services offered at the salon.
    Use this before suggesting a service to understand pricing and duration.
    
    Returns:
        JSON-formatted list of services with id, name, price, duration_minutes
    """
    db = SessionLocal()
    try:
        services = resolver_list_services(db, active_only=True)
        logger.info(f"Listed {len(services)} services")
        
        if not services:
            return "{\n  \"success\": true,\n  \"services\": [],\n  \"message\": \"No active services found in the system.\"\n}"
        
        # Format as readable text for agent
        formatted = "Available Services:\n\n"
        for service in services:
            formatted += f"• {service['name']}\n"
            formatted += f"  Price: ${service['price']:.2f}\n"
            formatted += f"  Duration: {service['duration_minutes']} minutes\n"
            if service.get('description'):
                formatted += f"  Description: {service['description']}\n"
            formatted += f"  ID: {service['id']}\n\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Error listing services: {str(e)}", exc_info=True)
        return f"{{\n  \"success\": false,\n  \"error\": \"Failed to list services: {str(e)}\"\n}}"
    finally:
        db.close()


def list_available_staff(branch_id: str = None, date: str = None, time: str = None) -> str:
    """
    Returns a list of all active staff members (stylists, etc.).
    Optionally filter by branch.
    
    Args:
        branch_id: Optional UUID of branch to filter staff
        date: Optional date string
        time: Optional time string
    
    Returns:
        JSON-formatted list of staff with id, name, role, branch_id
    """
    db = SessionLocal()
    try:
        import uuid
        
        parsed_branch_id = None
        if branch_id:
            try:
                parsed_branch_id = uuid.UUID(branch_id)
            except ValueError:
                logger.warning(f"Invalid branch_id format: {branch_id}")
        
        staff_list = resolver_list_staff(db, branch_id=parsed_branch_id, active_only=True)
        logger.info(f"Listed {len(staff_list)} staff members")
        
        if not staff_list:
            return "{\n  \"success\": true,\n  \"staff\": [],\n  \"message\": \"No active staff members found.\"\n}"
        
        # Format as readable text for agent
        formatted = "Available Staff:\n\n"
        for staff in staff_list:
            formatted += f"• {staff['name']} ({staff['role']})\n"
            formatted += f"  Email: {staff['email']}\n"
            formatted += f"  ID: {staff['id']}\n\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Error listing staff: {str(e)}", exc_info=True)
        return f"{{\n  \"success\": false,\n  \"error\": \"Failed to list staff: {str(e)}\"\n}}"
    finally:
        db.close()


def search_for_customers(search_query: str) -> str:
    """
    Search for existing customers by name, email, or phone number.
    Use before booking to find and verify customer identity.
    
    Args:
        search_query: Customer name, email, or phone number to search for
    
    Returns:
        JSON-formatted list of matching customers
    """
    db = SessionLocal()
    try:
        customers = resolver_search_customers(db, search_query, limit=10)
        logger.info(f"Found {len(customers)} matching customers")
        
        if not customers:
            return f"{{\n  \"success\": true,\n  \"customers\": [],\n  \"message\": \"No customers matching '{search_query}' found.\"\n}}"
        
        # Format as readable text for agent
        formatted = f"Search Results for '{search_query}':\n\n"
        for customer in customers:
            formatted += f"• {customer['name']}\n"
            formatted += f"  Email: {customer['email']}\n"
            formatted += f"  Phone: {customer.get('phone', 'N/A')}\n"
            formatted += f"  ID: {customer['id']}\n\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Error searching customers: {str(e)}", exc_info=True)
        return f"{{\n  \"success\": false,\n  \"error\": \"Failed to search customers: {str(e)}\"\n}}"
    finally:
        db.close()
