import asyncio
import os
import sys
from bson import ObjectId

sys.path.insert(0, r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend")
from dotenv import load_dotenv
load_dotenv(r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend\.env")

from app.database.connection import MongoDBManager
from app.repositories import FeedbackRepository, WorkspaceRepository, UserRepository, FeatureGroupRepository
from app.models.auth import User, Workspace
from app.models.feedback import FeedbackItem
from app.core.enums import PlatformRole, FeedbackCategory
from app.ai.agents.feedback_intelligence.service import FeedbackIntelligenceService
from app.ai.agents.feature_intelligence.service import FeatureIntelligenceService
from app.ai.agents.feature_intelligence.grouping import filter_eligible_feature_requests

async def test():
    db = await MongoDBManager.connect_async()
    user_repo = UserRepository(db)
    ws_repo = WorkspaceRepository(db)
    fb_repo = FeedbackRepository(db)
    fg_repo = FeatureGroupRepository(db)
    
    uid = ObjectId()
    wid = ObjectId()
    user = User(id=uid, name='Test', email=f't.{uid}@test.com', password_hash='password1234', platform_role=PlatformRole.USER)
    ws = Workspace(id=wid, name='TestWS', slug=f'test-{wid}', owner_id=uid)
    await user_repo.create(user)
    await ws_repo.create(ws)
    
    fb1 = FeedbackItem(
        id=ObjectId(),
        workspace_id=wid,
        customer_name='Finance Lead',
        title='Automated CSV and Excel scheduled export for compliance audits',
        description='We urgently require automated recurring CSV and Excel export functionality for our monthly financial compliance audits. Analysts spend 3 hours weekly manually dumping tables.',
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    fb2 = FeedbackItem(
        id=ObjectId(),
        workspace_id=wid,
        customer_name='Ops Lead',
        title='One-click CSV data export button on reporting tables',
        description='Please add a one-click CSV export button on reporting tables. Copy-pasting metrics manually is creating severe friction for our 20 analysts.',
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    fb3 = FeedbackItem(
        id=ObjectId(),
        workspace_id=wid,
        customer_name='Head of Analytics',
        title='Scheduled recurring CSV export automation for audit reporting',
        description='Need ability to schedule recurring CSV table report exports so our team can automate weekly data compliance audits without manual exports.',
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    await fb_repo.create(fb1)
    await fb_repo.create(fb2)
    await fb_repo.create(fb3)
    
    from app.ai.agents.feature_intelligence.schemas import FeatureRequestCandidate
    # Test with CSV export feedback (matches the live verification script)
    c1 = FeatureRequestCandidate(
        feedback_id=str(fb1.id),
        title=fb1.title,
        description=fb1.description,
        category="Feature Request",
        sentiment="Negative",
        urgency="High",
        customer_id="cust_1",
        customer_name="Finance Director @ AcquiredCorp",
        company_name="AcquiredCorp",
    )
    c2 = FeatureRequestCandidate(
        feedback_id=str(fb2.id),
        title=fb2.title,
        description=fb2.description,
        category="Feature Request",
        sentiment="Negative",
        urgency="High",
        customer_id="cust_2",
        customer_name="Operations Lead @ Apex Retail",
        company_name="Apex Retail",
    )
    c3 = FeatureRequestCandidate(
        feedback_id=str(fb3.id),
        title=fb3.title,
        description=fb3.description,
        category="Feature Request",
        sentiment="Neutral",
        urgency="High",
        customer_id="cust_3",
        customer_name="Head of Analytics @ NovaScale",
        company_name="NovaScale",
    )
    candidates = [c1, c2, c3]
    
    feat_service = FeatureIntelligenceService(feedback_repo=fb_repo, feature_group_repo=fg_repo, workspace_repo=ws_repo)
    print("Running group_feature_requests raw agent execute...")
    raw_agent_res = await feat_service.agent.execute(
        input_data={
            "candidates": candidates,
            "confidence_threshold": 0.5,
            "min_group_size": 1,
        },
        temperature=0.1,
    )
    print("Raw Agent Output:")
    print(raw_agent_res.data.model_dump_json(indent=2))
    
    # cleanup
    await user_repo.collection.delete_one({'_id': uid})
    await ws_repo.collection.delete_one({'_id': wid})
    await fb_repo.collection.delete_many({'workspaceId': wid})
    await fg_repo.collection.delete_many({'workspaceId': wid})

if __name__ == "__main__":
    asyncio.run(test())
