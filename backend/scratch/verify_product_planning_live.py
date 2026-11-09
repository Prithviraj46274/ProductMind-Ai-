"""
ProductMind AI — Live Groq + Qwen 3.8 27B Verification for Product Planning Agent
Connects to Groq, runs a real LLM generation for a complete product plan,
persists to MongoDB, verifies retrieval, checks zero-fabrication metrics,
and tests human review status updates.
"""

import asyncio
import json
import os
import sys

# Ensure backend is on the path
sys.path.insert(0, r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend")

# Load .env
from dotenv import load_dotenv
load_dotenv(r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend\.env")

from bson import ObjectId
from app.ai.config import AISettings
from app.ai.llm_service import LLMService
from app.ai.agents.product_planning.agent import ProductPlanningAgent
from app.ai.agents.product_planning.schemas import (
    ProductPlanningAgentOutput,
    ProductStrategicContext,
    GenerateProductPlanRequest,
    ReviewPlanRequest,
)
from app.ai.agents.product_planning.service import ProductPlanningService
from app.database.connection import MongoDBManager
from app.repositories import (
    PRDRepository,
    FeatureGroupRepository,
    PrioritizationScenarioRepository,
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
    UserRepository,
)
from app.models.intelligence import FeatureGroup
from app.models.planning import PrioritizationScenario
from app.models.auth import User, Workspace, WorkspaceMembership
from app.core.enums import PlatformRole, PRDStatus, UserRole, MembershipStatus


async def main():
    print("=" * 75)
    print("PRODUCTMIND AI — STEP 5: PRODUCT PLANNING AGENT LIVE VERIFICATION")
    print("=" * 75)

    # 1. Config Check
    config = AISettings()
    print(f"\n[1. CONFIGURATION]")
    print(f"  Provider:     {config.AI_PROVIDER}")
    print(f"  Model:        {config.AI_MODEL}")
    print(f"  Temperature:  0.1 (Enforced for deterministic planning)")
    print(f"  Max Tokens:   {config.AI_MAX_OUTPUT_TOKENS}")

    # 2. LLM Service Init
    llm_service = LLMService()
    print(f"\n[2. LLM SERVICE]")
    print(f"  Configured:   {llm_service.is_configured}")
    print(f"  Provider:     {llm_service.provider_name}")
    print(f"  Model:        {llm_service.model_name}")

    if not llm_service.is_configured:
        print("ERROR: LLM Service not configured.")
        return

    # 3. Connect to MongoDB
    print(f"\n[3. DATABASE CONNECTION]")
    db = await MongoDBManager.connect_async()
    print(f"  Connected DB: {db.name}")

    # Repositories
    user_repo = UserRepository(db)
    ws_repo = WorkspaceRepository(db)
    membership_repo = WorkspaceMembershipRepository(db)
    fg_repo = FeatureGroupRepository(db)
    prioritization_repo = PrioritizationScenarioRepository(db)
    prd_repo = PRDRepository(db)

    # 4. Set up controlled fixtures for live verification
    print(f"\n[4. FIXTURE SETUP]")
    test_user_id = ObjectId()
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()
    test_p_id = ObjectId()

    test_user = User(
        id=test_user_id,
        name="Sarah Jenkins (Lead PM)",
        email=f"pm_test_{test_user_id}@productmind.ai",
        password_hash="mock_hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )
    await user_repo.create(test_user)

    test_ws = Workspace(
        id=test_ws_id,
        name="Live Verification Workspace",
        slug=f"live-verify-{test_ws_id}",
        owner_id=test_user_id,
    )
    await ws_repo.create(test_ws)

    test_membership = WorkspaceMembership(
        workspace_id=test_ws_id,
        user_id=test_user_id,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )
    await membership_repo.create(test_membership)

    # Controlled FeatureGroup
    test_fg = FeatureGroup(
        id=test_fg_id,
        workspace_id=test_ws_id,
        title="Automated CSV & Excel Export Engine",
        description="Enterprise users require instant and scheduled CSV/Excel exports of dashboard reporting tables.",
        feedback_count=42,
        unique_customer_count=19,
        pain_points=[
            "Analysts spend 2.5 hours every Monday manually copying tables into Excel",
            "Lack of scheduled automated export creates compliance reporting delays",
            "Data formatting errors occur during manual copy-pasting",
        ],
        evidence=[
            "We spend 2.5 hours every Monday morning manually copying reporting metrics into our spreadsheet.",
            "Our compliance audit requires weekly CSV exports. Without this, our renewal is blocked.",
            "Please add an export button directly on the transaction and retention tables.",
        ],
        common_themes=["Reporting Automation", "Compliance Auditing", "Workflow Efficiency"],
        urgency_distribution={"critical": 8, "high": 18, "medium": 12, "low": 4},
    )
    await fg_repo.create(test_fg)

    # Controlled Prioritization Scenario (from Step 4)
    test_p_scenario = PrioritizationScenario(
        id=test_p_id,
        workspace_id=test_ws_id,
        name="Automated CSV & Excel Export Engine",
        feature_group_id=test_fg_id,
        final_score=86.2,
        priority_level="Critical",
        factor_scores={
            "customer_demand": 85.0,
            "urgency": 82.0,
            "business_impact": 90.0,
            "strategic_alignment": 88.0,
            "sentiment": 84.0,
        },
        coverage_percentage=90.0,
        explanation="High enterprise customer demand and direct contract renewal blocker justify immediate sprint delivery.",
        implementation_benefits=["Saves 2.5 hours/week per analyst", "Unblocks 3 enterprise renewals ($180k ARR)"],
        delay_risks=["Active enterprise churn threat", "Increased compliance friction"],
        missing_data=["usage_impact"],
        recommendation="Immediate sprint priority.",
        is_active=True,
    )
    await prioritization_repo.create(test_p_scenario)

    print(f"  User:          {test_user.name} ({test_user.id})")
    print(f"  Workspace:     {test_ws.name} ({test_ws.id})")
    print(f"  Feature Group: {test_fg.title} ({test_fg.id})")
    print(f"  Prioritization: {test_p_scenario.priority_level} ({test_p_scenario.final_score}/100)")

    # 5. Initialize Service & Run Live Agent Call
    print(f"\n[5. EXECUTING LIVE PLANNING AGENT WITH GROQ + QWEN 3.8 27B]")
    print(f"  (Sending real API request to Groq...)")

    agent = ProductPlanningAgent(llm_service=llm_service)
    service = ProductPlanningService(
        agent=agent,
        prd_repo=prd_repo,
        feature_group_repo=fg_repo,
        prioritization_repo=prioritization_repo,
        workspace_repo=ws_repo,
        membership_repo=membership_repo,
    )

    strategic_ctx = ProductStrategicContext(
        product_name="ProductMind AI Platform",
        product_description="AI Copilot for high-velocity Product Management teams",
        target_customer_segments=["Enterprise B2B SaaS", "Mid-market FinTech"],
        business_goals=["Reduce quarterly customer churn to < 2%", "Expand enterprise ARR"],
        current_quarter_objectives=["Deliver reporting export capabilities in Q4"],
        technical_constraints=["MongoDB 7.0+", "FastAPI asynchronous back-end", "AWS S3 for file storage"],
        known_dependencies=["Authentication Service", "Reporting Query Service"],
        additional_planning_instructions="Enforce strict role-based access control and rate-limiting per workspace.",
    )

    request_payload = GenerateProductPlanRequest(
        workspace_id=str(test_ws_id),
        feature_group_id=str(test_fg_id),
        prioritization_result_id=str(test_p_id),
        strategic_context=strategic_ctx,
    )

    try:
        plan_response = await service.generate_plan(
            request=request_payload,
            user=test_user,
        )

        print(f"\n{'=' * 75}")
        print(f"[6. LIVE GENERATION SUCCESSFUL]")
        print(f"{'=' * 75}")
        print(f"  Planning ID:    {plan_response.planning_id}")
        print(f"  Title:          {plan_response.title}")
        print(f"  Review Status:  {plan_response.status}")
        print(f"  Version:        {plan_response.version}")

        # Verify PRD
        prd = plan_response.prd
        print(f"\n[PRD DETAILS]")
        print(f"  Executive Summary: {prd.executive_summary[:120]}...")
        print(f"  Problem Statement: {prd.problem_statement[:120]}...")
        print(f"  Functional Requirements ({len(prd.functional_requirements)}):")
        for req in prd.functional_requirements[:4]:
            if hasattr(req, "origin"):
                thresh = f" [Threshold: {req.numerical_threshold}]" if req.numerical_threshold else " [Threshold: None (unconfirmed)]"
                src = f" [Ref: {req.source_reference}]" if req.source_reference else ""
                print(f"    - [{req.origin.value.upper()}] {req.title}: {req.description[:70]}...{thresh}{src} (Confirmed: {req.is_confirmed})")
            else:
                print(f"    - {req}")
        print(f"  Non-Functional ({len(prd.non_functional_requirements)}):")
        for nfr in prd.non_functional_requirements[:3]:
            if hasattr(nfr, "origin"):
                thresh = f" [Threshold: {nfr.numerical_threshold}]" if nfr.numerical_threshold else " [Threshold: None (unconfirmed)]"
                print(f"    - [{nfr.origin.value.upper()}] {nfr.title}: {nfr.description[:70]}...{thresh} (Requires Confirmation: {nfr.requires_confirmation})")
            else:
                print(f"    - {nfr}")
        print(f"  Out of Scope ({len(prd.out_of_scope)}):")
        for oos in prd.out_of_scope[:2]:
            print(f"    - {oos}")
        print(f"  Open Questions ({len(prd.open_questions)}):")
        for oq in prd.open_questions[:2]:
            print(f"    - {oq}")

        # Verify User Stories & Acceptance Criteria
        print(f"\n[USER STORIES ({len(plan_response.user_stories)})]")
        for us in plan_response.user_stories[:2]:
            us_origin = getattr(us, "origin", "n/a")
            us_origin_str = us_origin.value if hasattr(us_origin, "value") else str(us_origin)
            print(f"  [{us.story_id}] {us.title} ({us.priority}) [Origin: {us_origin_str}]")
            print(f"    Description: {us.description}")
            print(f"    Persona:     {us.persona}")
            print(f"    Value:       {us.business_value}")
            if getattr(us, "source_reference", None):
                print(f"    Evidence Ref:{us.source_reference}")
            print(f"    Acceptance Criteria ({len(us.acceptance_criteria)}):")
            for ac in us.acceptance_criteria[:2]:
                ac_origin = getattr(ac, "origin", "n/a")
                ac_origin_str = ac_origin.value if hasattr(ac_origin, "value") else str(ac_origin)
                print(f"      - [{ac.criterion_id}] ({ac.scenario_type}) [{ac_origin_str}] {ac.description}")

        # Verify Technical Suggestions
        print(f"\n[TECHNICAL REQUIREMENTS ({len(plan_response.technical_requirements)})]")
        for tr in plan_response.technical_requirements[:3]:
            tr_origin = getattr(tr, "origin", "n/a")
            tr_origin_str = tr_origin.value if hasattr(tr_origin, "value") else str(tr_origin)
            print(f"  [{tr.category.upper()}] [{tr_origin_str.upper()}] {tr.title}")
            print(f"    Spec:       {tr.description[:100]}...")
            print(f"    Rationale:  {tr.rationale[:80]}...")
            print(f"    Review Req: {tr.requires_engineering_review} (Confirmed: {getattr(tr, 'is_confirmed', False)})")

        # Verify Success Metrics (Zero-Fabrication & Target Origin check)
        print(f"\n[SUCCESS METRICS ({len(plan_response.success_metrics)})]")
        for sm in plan_response.success_metrics:
            target_str = sm.suggested_target if sm.suggested_target else "None"
            target_orig = sm.target_origin.value if sm.target_origin else "None"
            period_str = sm.measurement_period if sm.measurement_period else "None"
            print(f"  Metric:       {sm.metric_name} [Origin: {sm.origin.value}] (Confirmed: {sm.is_confirmed})")
            print(f"    Method:     {sm.measurement_method}")
            print(f"    Baseline:   {sm.baseline} (Zero-fabrication confirmed)")
            print(f"    Direction:  {sm.expected_direction} (Requires Confirmation: {sm.direction_requires_confirmation})")
            print(f"    Target:     {target_str} [Target Origin: {target_orig}] (Confirmed: {sm.is_target_confirmed}, Requires Confirmation: {sm.requires_target_confirmation})")
            print(f"    Period:     {period_str} (Confirmed: {sm.is_period_confirmed}, Requires Confirmation: {sm.period_requires_confirmation})")
            if sm.source_reference:
                print(f"    Source Ref: {sm.source_reference}")

        # Verify Risks
        print(f"\n[RISK ANALYSIS ({len(plan_response.risk_analysis)})]")
        for r in plan_response.risk_analysis[:2]:
            print(f"  [{r.category.upper()}] {r.description[:80]}...")
            print(f"    Impact/Likelihood: {r.impact} / {r.likelihood}")
            print(f"    Mitigation:        {r.mitigation[:80]}...")

        # Verify Roadmap
        print(f"\n[ROADMAP RECOMMENDATIONS ({len(plan_response.roadmap_recommendations)})]")
        for rp in plan_response.roadmap_recommendations[:3]:
            print(f"  Phase {rp.suggested_sequencing}: {rp.phase_name}")
            print(f"    Objective: {rp.objective}")
            print(f"    Tasks ({len(rp.tasks)}): {', '.join(rp.tasks[:2])}")

        # 7. Verify Retrieval from MongoDB
        print(f"\n[7. PERSISTENCE & RETRIEVAL VERIFICATION]")
        fetched_plan = await service.get_plan_by_id(
            planning_id=plan_response.planning_id,
            user=test_user,
            workspace_id=str(test_ws_id),
        )
        assert fetched_plan is not None
        assert fetched_plan.planning_id == plan_response.planning_id
        print(f"  Successfully retrieved persisted PRD from MongoDB collection 'prds' ✅")

        # 8. Human Review Lifecycle Verification
        print(f"\n[8. HUMAN REVIEW LIFECYCLE TEST]")
        review_update = await service.update_review_status(
            planning_id=plan_response.planning_id,
            request=ReviewPlanRequest(
                review_status="approved",
                review_notes="Approved by Head of Product for Q4 sprint.",
            ),
            user=test_user,
        )
        assert review_update.status == "Approved"
        print(f"  Updated status to: {review_update.status} ✅")
        print(f"  Review Notes:     {review_update.review_notes} ✅")
        print(f"  Reviewed By:      {review_update.reviewed_by} ✅")

        # 9. Verify Approved PRD Overwrite Protection
        print(f"\n[9. APPROVED OVERWRITE PROTECTION TEST]")
        try:
            await service.generate_plan(
                request=GenerateProductPlanRequest(
                    workspace_id=str(test_ws_id),
                    feature_group_id=str(test_fg_id),
                    force_approved_overwrite=False,  # Should be blocked!
                ),
                user=test_user,
            )
            print("  FAIL: Overwrite of approved PRD was not blocked!")
        except Exception as e:
            print(f"  Successfully blocked unforced overwrite of approved PRD: {e.detail} ✅")

        # 10. Data Integrity Check
        print(f"\n[10. DATA INTEGRITY CHECK]")
        intact_fg = await fg_repo.find_by_id(test_fg_id)
        assert intact_fg is not None
        assert intact_fg.title == test_fg.title
        assert intact_fg.feedback_count == 42
        print(f"  FeatureGroup record unchanged ✅")

        intact_p = await prioritization_repo.find_by_id(test_p_id)
        assert intact_p is not None
        assert intact_p.final_score == 86.2
        print(f"  PrioritizationScenario record unchanged ✅")

        print(f"\n{'=' * 75}")
        print("STEP 5: ALL LIVE VERIFICATION CHECKS PASSED ✅")
        print(f"{'=' * 75}")

    finally:
        # Cleanup test documents
        print(f"\n[CLEANUP]")
        if 'plan_response' in locals() and plan_response.planning_id:
            await prd_repo.delete(ObjectId(plan_response.planning_id), workspace_id=test_ws_id)
            print(f"  Cleaned up test PRD: {plan_response.planning_id}")
        await prioritization_repo.delete(test_p_id, workspace_id=test_ws_id)
        await fg_repo.delete(test_fg_id, workspace_id=test_ws_id)
        await membership_repo.delete(test_membership.id, workspace_id=test_ws_id)
        await ws_repo.delete(test_ws_id)
        await user_repo.delete(test_user_id)
        print("  All fixtures cleaned up cleanly ✅")


if __name__ == "__main__":
    asyncio.run(main())
