"""
Handler Layer — Phase 2 Architecture.

Each handler is a single-responsibility class that processes exactly one
business operation within a workflow. Workflows dispatch to handlers
dynamically through the WorkflowRegistry.

Handler naming convention: <Action><Domain>Handler
All handlers implement the BaseHandler interface.
"""

from handlers.appointment_handlers import (
    BookAppointmentHandler,
    ListAppointmentsHandler,
    CancelAppointmentHandler,
    RescheduleAppointmentHandler,
    CheckAvailabilityHandler,
    ListServicesHandler,
    ListStaffHandler,
    SearchCustomersHandler,
)

from handlers.crm_handlers import (
    CreateLeadHandler,
    SearchLeadsHandler,
    AdvanceLeadHandler,
    SendFollowupHandler,
    GenerateMessageHandler,
    DetectAbandonedHandler,
    ConversionAnalyticsHandler,
    PipelineSnapshotHandler,
)

from handlers.analytics_handlers import (
    DashboardHandler,
    RevenueHandler,
    CustomerMetricsHandler,
    StaffPerformanceHandler,
    LeadAnalyticsHandler,
    ReviewAnalyticsHandler,
    UpsellAnalyticsHandler,
    ForecastHandler,
    AIInsightsHandler,
    BusinessContextHandler,
    RawSQLHandler,
    CohortRemindersHandler,
)

from handlers.reputation_handlers import (
    GetReviewsHandler,
    ReviewAnalyticsHandler as ReputationAnalyticsHandler,
    CriticalReviewsHandler,
    DraftResponseHandler,
    ReputationScorecardHandler,
    EscalateReviewHandler,
)

from handlers.recommendation_handlers import (
    GetRecommendationsHandler,
    AcceptRecommendationHandler,
    RejectRecommendationHandler,
    UpsellAnalyticsHandler as RecommendationAnalyticsHandler,
)

from handlers.staff_handlers import (
    GetScheduleHandler,
    TodayScheduleHandler,
    NextCustomerHandler,
    CustomerHistoryHandler,
    CustomerPreferencesHandler,
    StaffRevenueHandler,
    StaffPerformanceHandler as StaffKPIHandler,
    PendingAppointmentsHandler,
    CreateLeaveHandler,
    SendRemindersHandler,
)

__all__ = [
    # Appointment
    "BookAppointmentHandler",
    "ListAppointmentsHandler",
    "CancelAppointmentHandler",
    "RescheduleAppointmentHandler",
    "CheckAvailabilityHandler",
    "ListServicesHandler",
    "ListStaffHandler",
    "SearchCustomersHandler",
    # CRM
    "CreateLeadHandler",
    "SearchLeadsHandler",
    "AdvanceLeadHandler",
    "SendFollowupHandler",
    "GenerateMessageHandler",
    "DetectAbandonedHandler",
    "ConversionAnalyticsHandler",
    "PipelineSnapshotHandler",
    # Analytics
    "DashboardHandler",
    "RevenueHandler",
    "CustomerMetricsHandler",
    "StaffPerformanceHandler",
    "LeadAnalyticsHandler",
    "ReviewAnalyticsHandler",
    "UpsellAnalyticsHandler",
    "ForecastHandler",
    "AIInsightsHandler",
    "BusinessContextHandler",
    "RawSQLHandler",
    "CohortRemindersHandler",
    # Reputation
    "ReputationAnalyticsHandler",
    "CriticalReviewsHandler",
    "DraftResponseHandler",
    "ReputationScorecardHandler",
    "EscalateReviewHandler",
    # Recommendations
    "GetRecommendationsHandler",
    "AcceptRecommendationHandler",
    "RejectRecommendationHandler",
    "RecommendationAnalyticsHandler",
    # Staff
    "GetScheduleHandler",
    "TodayScheduleHandler",
    "NextCustomerHandler",
    "CustomerHistoryHandler",
    "CustomerPreferencesHandler",
    "StaffRevenueHandler",
    "StaffKPIHandler",
    "PendingAppointmentsHandler",
    "CreateLeaveHandler",
    "SendRemindersHandler",
]
