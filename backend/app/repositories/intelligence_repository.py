"""
ProductMind AI — Intelligence, Persona & Experiment Repositories
"""

from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database.collections import Collections
from app.models.intelligence import FeatureGroup, CustomerPersona, CompetitorIntel
from app.models.planning import ProductExperiment, CustomerJourney, PrioritizationScenario
from app.repositories.base import BaseRepository


class FeatureGroupRepository(BaseRepository[FeatureGroup]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.FEATURE_GROUPS, FeatureGroup)

    async def find_ranked_by_feedback(self, workspace_id: Any) -> List[FeatureGroup]:
        return await self.find_by_workspace(
            workspace_id,
            sort=[("feedbackCount", -1)],
        )

    async def find_by_workspace_and_filters(
        self,
        workspace_id: Any,
        status: Optional[str] = None,
        min_feedback_count: Optional[int] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[FeatureGroup]:
        filter_query: Dict[str, Any] = {}
        if status:
            filter_query["status"] = status
        if min_feedback_count is not None and min_feedback_count > 0:
            filter_query["feedbackCount"] = {"$gte": min_feedback_count}

        return await self.find_by_workspace(
            workspace_id,
            filter_query=filter_query,
            sort=[("feedbackCount", -1), ("createdAt", -1)],
            limit=limit,
            skip=skip,
        )

    async def find_by_related_feedback(
        self,
        workspace_id: Any,
        feedback_id: Any,
    ) -> Optional[FeatureGroup]:
        ws_oid = self._ensure_object_id(workspace_id)
        f_oid = self._ensure_object_id(feedback_id)
        doc = await self.collection.find_one({
            "workspaceId": ws_oid,
            "relatedFeedbackIds": f_oid,
        })
        return self.model_cls.from_mongo(doc) if doc else None


class CustomerPersonaRepository(BaseRepository[CustomerPersona]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.CUSTOMER_PERSONAS, CustomerPersona)

    async def find_favorites(self, workspace_id: Any) -> List[CustomerPersona]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"isFavorite": True},
            sort=[("name", 1)],
        )


class CompetitorIntelRepository(BaseRepository[CompetitorIntel]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.COMPETITOR_INTEL, CompetitorIntel)


class ProductExperimentRepository(BaseRepository[ProductExperiment]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.PRODUCT_EXPERIMENTS, ProductExperiment)


class CustomerJourneyRepository(BaseRepository[CustomerJourney]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.CUSTOMER_JOURNEYS, CustomerJourney)

    async def find_ordered_stages(self, workspace_id: Any) -> List[CustomerJourney]:
        return await self.find_by_workspace(
            workspace_id,
            sort=[("order", 1)],
        )


class PrioritizationScenarioRepository(BaseRepository[PrioritizationScenario]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.PRIORITIZATION_SCENARIOS, PrioritizationScenario)

    async def find_by_workspace_and_feature_group(
        self,
        workspace_id: Any,
        feature_group_id: Any,
    ) -> Optional[PrioritizationScenario]:
        """Finds the most recent active prioritization result for a specific feature group."""
        ws_oid = self._ensure_object_id(workspace_id)
        fg_oid = self._ensure_object_id(feature_group_id)
        doc = await self.collection.find_one({
            "workspaceId": ws_oid,
            "featureGroupId": fg_oid,
            "isActive": True,
        })
        return self.model_cls.from_mongo(doc) if doc else None

    async def find_active_by_workspace(
        self,
        workspace_id: Any,
        limit: int = 100,
        skip: int = 0,
    ) -> List[PrioritizationScenario]:
        """Retrieves active prioritization results for a workspace."""
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"isActive": True},
            sort=[("finalScore", -1), ("createdAt", -1)],
            limit=limit,
            skip=skip,
        )

    async def find_ranked_by_score(
        self,
        workspace_id: Any,
        limit: int = 100,
        skip: int = 0,
    ) -> List[PrioritizationScenario]:
        """Retrieves prioritization results ordered by final numerical score descending."""
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"isActive": True, "finalScore": {"$ne": None}},
            sort=[("finalScore", -1)],
            limit=limit,
            skip=skip,
        )

