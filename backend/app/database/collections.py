"""
ProductMind AI — Central MongoDB Collection Name Registry
Guarantees exact matching with existing MongoDB collections.
"""


class Collections:
    # Auth & Workspace
    USERS = "users"
    WORKSPACES = "workspaces"
    WORKSPACE_MEMBERSHIPS = "workspace_memberships"
    AUTH_SESSIONS = "auth_sessions"

    # Feedback & Ingestion
    FEEDBACK_BATCHES = "feedback_batches"
    FEEDBACK_ITEMS = "feedback_items"

    # Product Analytics
    ANALYTICS_BATCHES = "analytics_batches"
    ANALYTICS_EVENTS = "analytics_events"
    ANALYTICS_DAILY_ROLLUPS = "analytics_daily_rollups"

    # Intelligence & Clustering
    FEATURE_GROUPS = "feature_groups"
    CUSTOMER_PERSONAS = "customer_personas"
    COMPETITOR_INTEL = "competitor_intel"

    # Planning, Prioritization, PRD & Roadmap
    FEATURES = "features"
    PRIORITIZATION_SCENARIOS = "prioritization_scenarios"
    PRDS = "prds"
    ROADMAP_ITEMS = "roadmap_items"
    RELEASES = "releases"
    PRODUCT_EXPERIMENTS = "product_experiments"
    CUSTOMER_JOURNEYS = "customer_journeys"

    # Copilot
    COPILOT_CONVERSATIONS = "copilot_conversations"
    COPILOT_MESSAGES = "copilot_messages"

    # Reporting & Audit
    SAVED_REPORTS = "saved_reports"
    AUDIT_LOGS = "audit_logs"

    @classmethod
    def all_collections(cls):
        """Returns all 23 collection names defined in the architecture."""
        return [
            cls.USERS,
            cls.WORKSPACES,
            cls.WORKSPACE_MEMBERSHIPS,
            cls.AUTH_SESSIONS,
            cls.FEEDBACK_BATCHES,
            cls.FEEDBACK_ITEMS,
            cls.ANALYTICS_BATCHES,
            cls.ANALYTICS_EVENTS,
            cls.ANALYTICS_DAILY_ROLLUPS,
            cls.FEATURE_GROUPS,
            cls.CUSTOMER_PERSONAS,
            cls.COMPETITOR_INTEL,
            cls.FEATURES,
            cls.PRIORITIZATION_SCENARIOS,
            cls.PRDS,
            cls.ROADMAP_ITEMS,
            cls.RELEASES,
            cls.PRODUCT_EXPERIMENTS,
            cls.CUSTOMER_JOURNEYS,
            cls.COPILOT_CONVERSATIONS,
            cls.COPILOT_MESSAGES,
            cls.SAVED_REPORTS,
            cls.AUDIT_LOGS,
        ]

