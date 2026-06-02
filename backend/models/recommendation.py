"""
Recommendation models for SalonAI Workforce Platform.
Exposes ServiceRecommendation and CustomerRecommendation structures.
"""

from db.models import ServiceRecommendation, CustomerRecommendation

__all__ = ["ServiceRecommendation", "CustomerRecommendation"]
