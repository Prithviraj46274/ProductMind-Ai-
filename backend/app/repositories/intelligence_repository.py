"""
ProductMind AI — Intelligence, Persona & Experiment Repositories
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

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

