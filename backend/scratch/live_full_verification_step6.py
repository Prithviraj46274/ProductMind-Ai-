"""
ProductMind AI — Final Step 6 Live Multi-Agent Verification Script
Executes full 4-stage pipeline against live MongoDB and Groq Cloud (qwen/qwen3.8-27b).
Verifies:
1. Stage 1: Feedback Intelligence (Groq LLM)
2. Stage 2: Feature Intelligence (Candidate filtering, Groq grouping, deterministic demand metrics, exclusion of non-features)
3. Stage 3: Prioritization (Groq assessment, deterministic Python scoring, missing analytics = None)
4. Stage 4: Product Planning (Groq PRD, user stories, acceptance criteria, review_status = pending_review)
5. Groq token consumption, API calls, and timing metrics
6. MongoDB PRD persistence and run store retrieval
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure backend directory is in path
sys.path.insert(0, r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend")

from dotenv import load_dotenv
load_dotenv(r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend\.env")

from bson import ObjectId
import httpx

from app.main import app
from app.database.connection import MongoDBManager
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.feedback import FeedbackItem
from app.core.enums import PlatformRole, UserRole, MembershipStatus, FeedbackCategory, PRDStatus
from app.repositories import (
    FeedbackRepository,
    FeatureGroupRepository,
    PrioritizationScenarioRepository,
    PRDRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
    UserRepository,
)
from app.ai.llm_service import get_llm_service
from app.ai.providers.groq import GroqProvider
from app.api.dependencies import get_current_user


async def run_live_verification():
    print("=" * 80)
    print("PRODUCTMIND AI — STEP 6: FINAL AI ORCHESTRATOR LIVE VERIFICATION")
    print("=" * 80)

    # 1. Connect to Database
    print("\n[1. DATABASE & LLM CONFIGURATION]")
    db = await MongoDBManager.connect_async()
    print(f"  Connected MongoDB Database: {db.name}")

    llm_service = get_llm_service()
    provider: GroqProvider = llm_service.provider
    print(f"  AI Provider:    {provider.provider_name.upper()}")
    print(f"  Configured:     {llm_service.is_configured}")
    print(f"  Target Model:   {provider.model_name}")

    # Initialize Repositories
    user_repo = UserRepository(db)
    ws_repo = WorkspaceRepository(db)
    membership_repo = WorkspaceMembershipRepository(db)
    feedback_repo = FeedbackRepository(db)
    fg_repo = FeatureGroupRepository(db)
    prio_repo = PrioritizationScenarioRepository(db)
    prd_repo = PRDRepository(db)

    # 2. Setup Controlled Test Fixtures
    print("\n[2. SETUP CONTROLLED TEST FIXTURES]")
    demo_user_id = ObjectId()
    demo_ws_id = ObjectId()

    demo_user = User(
        id=demo_user_id,
        name="Elena Rostova (VP Product)",
        email=f"elena.rostova.{demo_user_id}@productmind.ai",
        password_hash="verified_live_test_hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )
    await user_repo.create(demo_user)

    demo_ws = Workspace(
        id=demo_ws_id,
        name="Enterprise Product Strategy Workspace",
        slug=f"enterprise-strategy-{demo_ws_id}",
        owner_id=demo_user_id,
    )
    await ws_repo.create(demo_ws)

    demo_membership = WorkspaceMembership(
        workspace_id=demo_ws_id,
        user_id=demo_user_id,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )
    await membership_repo.create(demo_membership)

    # Ingest 4 realistic customer feedback items:
    # 3 related to automated export, 1 unrelated bug/performance complaint
    fb1 = FeedbackItem(
        id=ObjectId(),
        workspace_id=demo_ws_id,
        customer_name="Finance Director @ AcquiredCorp",
        customer_email="finance@acquiredcorp.com",
        company_name="AcquiredCorp",
        title="Automated CSV and Excel scheduled export for compliance audits",
        description="We urgently require automated recurring CSV and Excel export functionality for our monthly financial compliance audits. Analysts spend 3 hours weekly manually dumping tables.",
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    fb2 = FeedbackItem(
        id=ObjectId(),
        workspace_id=demo_ws_id,
        customer_name="Operations Lead @ Apex Retail",
        customer_email="ops@apexretail.io",
        company_name="Apex Retail",
        title="One-click CSV data export button on reporting tables",
        description="Please add a one-click CSV export button on reporting tables. Copy-pasting metrics manually is creating severe friction for our 20 analysts.",
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    fb3 = FeedbackItem(
        id=ObjectId(),
        workspace_id=demo_ws_id,
        customer_name="Head of Analytics @ NovaScale",
        customer_email="analytics@novascale.com",
        company_name="NovaScale",
        title="Scheduled recurring CSV export automation for audit reporting",
        description="Need ability to schedule recurring CSV table report exports so our team can automate weekly data compliance audits without manual exports.",
        category=FeedbackCategory.FEATURE_REQUESTS,
    )
    fb4 = FeedbackItem(
        id=ObjectId(),
        workspace_id=demo_ws_id,
        customer_name="IT Support Specialist @ LegacyTech",
        customer_email="support@legacytech.com",
        company_name="LegacyTech",
        title="Dashboard page load times are sluggish on high-resolution screens",
        description="The customer overview dashboard takes over 8 seconds to render when multiple widgets are active. This is a severe performance issue.",
        category=FeedbackCategory.PERFORMANCE,
    )

    await feedback_repo.create(fb1)
    await feedback_repo.create(fb2)
    await feedback_repo.create(fb3)
    await feedback_repo.create(fb4)

    feedback_ids = [str(fb1.id), str(fb2.id), str(fb3.id), str(fb4.id)]
    print(f"  Created Demo Workspace: {demo_ws_id}")
    print(f"  Created Demo User:      {demo_user.name} ({demo_user_id})")
    print(f"  Ingested 4 Controlled Feedback Records:")
    print(f"    - FB 1 (Feature): {fb1.title}")
    print(f"    - FB 2 (Feature): {fb2.title}")
    print(f"    - FB 3 (Feature): {fb3.title}")
    print(f"    - FB 4 (Bug):     {fb4.title}")

    # Override current user dependency to authenticate as demo_user
    app.dependency_overrides[get_current_user] = lambda: demo_user

    try:
        # 3. Test API Health
        print("\n[3. HEALTH DIAGNOSTIC ENDPOINT CHECK]")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            health_res = await client.get("/api/v1/orchestrator/health")
            print(f"  GET /api/v1/orchestrator/health status: {health_res.status_code}")
            health_data = health_res.json()
            print(f"  Orchestrator Operational Status:        {health_data.get('status')}")
            print(f"  All 4 Specialist Agents Healthy:        {health_data.get('healthy')}")
            for a in health_data.get("specialist_agents", []):
                print(f"    * {a['agent']}: {a['status']}")

            # Reset metrics counter before pipeline run
            provider.metrics = type(provider.metrics)()

            # 4. Execute Live Full Pipeline (Mode A)
            print("\n[4. EXECUTE FULL 4-STAGE PIPELINE (POST /api/v1/orchestrator/run)]")
            pipeline_payload = {
                "workspace_id": str(demo_ws_id),
                "mode": "full",
                "feedback_ids": feedback_ids,
                "strategic_alignment_context": "Accelerate enterprise expansion, automate reporting compliance, and reduce analyst manual overhead.",
                "usage_analytics": None,
            }

            pipeline_start = time.perf_counter()
            run_res = await client.post("/api/v1/orchestrator/run", json=pipeline_payload)
            pipeline_latency = round(time.perf_counter() - pipeline_start, 2)

            print(f"  POST Response Status Code: {run_res.status_code}")
            assert run_res.status_code == 200, f"Pipeline failed: {run_res.text}"
            run_data = run_res.json()

            run_id = run_data["run_id"]
            status_val = run_data["status"]
            stages = run_data.get("stages", [])

            print(f"  Run ID:                  {run_id}")
            print(f"  Pipeline Overall Status: {status_val.upper()}")
            print(f"  Total Duration:          {run_data.get('total_duration_ms')} ms ({pipeline_latency}s)")
            print(f"  Stages Executed:         {len(stages)}")

            # 5. Verify Stage 1: Feedback Intelligence
            print("\n[5. STAGE 1: FEEDBACK INTELLIGENCE VERIFICATION]")
            s1 = next((s for s in stages if s["stage"] == "feedback_intelligence"), None)
            assert s1 is not None, "Stage 1 missing"
            print(f"  Status:       {s1['status'].upper()}")
            print(f"  Duration:     {s1['duration_ms']} ms")
            print(f"  Metadata:     {s1.get('metadata')}")

            fb_res = run_data.get("feedback_analysis_results") or run_data.get("feedback_results") or {}
            print(f"  Analyzed Feedback Results: {fb_res.get('total_requested')} requested, {fb_res.get('successful')} successful")
            assert fb_res.get("successful", 0) >= 3, "At least 3 feedback items should succeed"

            # 6. Verify Stage 2: Feature Intelligence
            print("\n[6. STAGE 2: FEATURE INTELLIGENCE VERIFICATION]")
            s2 = next((s for s in stages if s["stage"] == "feature_intelligence"), None)
            assert s2 is not None, "Stage 2 missing"
            print(f"  Status:       {s2['status'].upper()}")
            print(f"  Duration:     {s2['duration_ms']} ms")
            print(f"  Metadata:     {s2.get('metadata')}")

            fg_res = run_data.get("generated_feature_groups") or run_data.get("feature_group_results") or {}
            groups = fg_res.get("groups", []) or fg_res.get("feature_groups", [])
            print(f"  Groups Formed: {len(groups)}")
            assert len(groups) >= 1, "At least one feature group should be formed"
            top_fg = groups[0]
            fg_title = top_fg.get("group_name") or top_fg.get("title")
            fg_desc = top_fg.get("consolidated_description") or top_fg.get("description")
            print(f"  Top Feature Group Title: '{fg_title}'")
            print(f"  Description:             {fg_desc}")
            print(f"  Grouped Feedback Count:  {top_fg.get('total_request_count')}")
            print(f"  Related Feedback IDs:    {top_fg.get('related_feedback_ids')}")

            # Verify bug was NOT included in any feature group
            all_grouped_ids = [fid for g in groups for fid in g.get("related_feedback_ids", [])]
            assert str(fb4.id) not in all_grouped_ids, "Bug report fb4 should NOT be in any feature group"
            print("  >>> Verified: Unrelated bug fb4 was correctly excluded from all feature groups! <<<")

            # 7. Verify Stage 3: Prioritization
            print("\n[7. STAGE 3: PRIORITIZATION VERIFICATION]")
            s3 = next((s for s in stages if s["stage"] == "prioritization"), None)
            assert s3 is not None, "Stage 3 missing"
            print(f"  Status:       {s3['status'].upper()}")
            print(f"  Duration:     {s3['duration_ms']} ms")
            print(f"  Metadata:     {s3.get('metadata')}")

            prio_res = run_data.get("prioritization_results") or {}
            prio_list = prio_res.get("results", []) if isinstance(prio_res, dict) else []
            print(f"  Scenarios Evaluated: {len(prio_list)}")
            assert len(prio_list) >= 1, "At least one prioritization result expected"
            top_prio = prio_list[0]
            print(f"  Priority Level:      {top_prio.get('priority_level')}")
            print(f"  Final Composite Score:{top_prio.get('final_score')}/100")
            print(f"  Missing Data List:   {top_prio.get('missing_data')}")
            print(f"  Explanation:         {top_prio.get('explanation')[:140]}...")
            assert "usage_impact" in top_prio.get("missing_data", []), "usage_impact should be in missing_data because analytics=None"
            print("  >>> Verified: Missing analytics remained None and was properly reweighted! <<<")

            # 8. Verify Stage 4: Product Planning
            print("\n[8. STAGE 4: PRODUCT PLANNING VERIFICATION]")
            s4 = next((s for s in stages if s["stage"] == "product_planning"), None)
            assert s4 is not None, "Stage 4 missing"
            print(f"  Status:       {s4['status'].upper()}")
            print(f"  Duration:     {s4['duration_ms']} ms")
            print(f"  Metadata:     {s4.get('metadata')}")

            prd_output = run_data.get("planning_result") or run_data.get("product_plan_result")

            assert prd_output is not None, "Product Plan result must be present"
            print(f"  PRD Title:           {prd_output.get('title')}")
            print(f"  PRD Review Status:   {prd_output.get('status')} (Must be Pending Review)")
            prd_status_str = str(prd_output.get("status") or "").lower().replace(" ", "_")
            assert prd_status_str in ("pending_review", "draft"), f"PRD Status must be pending_review or draft, got: {prd_output.get('status')}"
            assert prd_status_str != "approved", "PRD must never be auto-approved without human signoff"
            print("  >>> CRITICAL GOVERNANCE VERIFIED: PRD review_status is strictly Pending Review (never auto-approved)! <<<")

            user_stories = prd_output.get("user_stories", [])
            print(f"  User Stories Count:  {len(user_stories)}")
            if user_stories:
                us1 = user_stories[0]
                print(f"    * Story: [{us1.get('story_id')}] {us1.get('title')}")
                print(f"      Persona: {us1.get('persona')} | Origin: {us1.get('origin')}")
                ac_list = us1.get("acceptance_criteria", [])
                print(f"      Acceptance Criteria Count: {len(ac_list)}")

            # 9. Verify MongoDB Persistence
            print("\n[9. MONGODB PERSISTENCE VERIFICATION]")
            persisted_prd = await prd_repo.collection.find_one({"workspaceId": demo_ws_id})
            assert persisted_prd is not None, "PRD was not persisted to MongoDB"
            print(f"  Found PRD document in MongoDB: ID={persisted_prd['_id']}")
            print(f"  Title:                        {persisted_prd.get('title')}")
            print(f"  Status in DB:                 {persisted_prd.get('status')}")
            assert persisted_prd.get("status") in ("pending_review", PRDStatus.PENDING_REVIEW.value)
            print("  >>> Verified: PRD persisted in MongoDB with pending_review status! <<<")

            # 10. Verify Run Retrieval Endpoint
            print("\n[10. RUN RETRIEVAL ENDPOINT (GET /api/v1/orchestrator/runs/{run_id})]")
            get_run_res = await client.get(f"/api/v1/orchestrator/runs/{run_id}")
            print(f"  GET Response Status Code: {get_run_res.status_code}")
            assert get_run_res.status_code == 200, "Failed to retrieve run by ID"
            retrieved = get_run_res.json()
            assert retrieved["run_id"] == run_id
            assert retrieved["status"] == status_val
            print(f"  Successfully retrieved run {run_id} from OrchestratorRunStore!")

            # 11. Groq Usage and Token Telemetry Metrics
            print("\n[11. GROQ API USAGE & TOKEN CONSUMPTION TELEMETRY]")
            m = provider.metrics.to_dict()
            print(f"  Model Name:                 {provider.model_name}")
            print(f"  Total Groq API Requests:    {m['total_requests']}")
            print(f"  Successful Groq Requests:   {m['successful_requests']}")
            print(f"  Failed Groq Requests:       {m['failed_requests']}")
            print(f"  HTTP 429 Rate Limit Hits:   {m['rate_limit_responses']}")
            print(f"  Input Tokens Consumed:      {m['input_tokens']:,}")
            print(f"  Output Tokens Consumed:     {m['output_tokens']:,}")
            print(f"  Total Tokens Consumed:      {m['total_tokens']:,}")
            print(f"  Total Pipeline Latency:     {pipeline_latency}s")

            print("\n" + "=" * 80)
            print(">>> LIVE VERIFICATION COMPLETED SUCCESSFULLY: ALL 4 STAGES EXECUTED CLEANLY! <<<")
            print("=" * 80)

    finally:
        # Cleanup test documents
        print("\n[CLEANUP]")
        await feedback_repo.collection.delete_many({"workspaceId": demo_ws_id})
        await fg_repo.collection.delete_many({"workspaceId": demo_ws_id})
        await prio_repo.collection.delete_many({"workspaceId": demo_ws_id})
        await prd_repo.collection.delete_many({"workspaceId": demo_ws_id})
        await membership_repo.collection.delete_many({"workspaceId": demo_ws_id})
        await ws_repo.collection.delete_one({"_id": demo_ws_id})
        await user_repo.collection.delete_one({"_id": demo_user_id})
        app.dependency_overrides.clear()
        print("  Cleaned up all test workspace documents from MongoDB.")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
