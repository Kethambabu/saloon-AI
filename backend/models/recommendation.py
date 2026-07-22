"""
Recommendation models for SalonAI Workforce Platform.
Exposes ServiceRecommendation and CustomerRecommendation structures.
"""

from infrastructure.db.models import ServiceRecommendation, CustomerRecommendation

__all__ = ["ServiceRecommendation", "CustomerRecommendation"]

