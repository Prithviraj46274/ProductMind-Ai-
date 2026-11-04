"""
ProductMind AI — Python Database Seeder & Data Ingestion Script
Replaces server/src/database/seed/seedDatabase.js.

Connects to MongoDB, validates against existing records, reads seed data,
hashes passwords securely with bcrypt, resolves cross-collection relational references,
and populates the database idempotently.
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
import sys
from typing import Any, Dict, List, Optional
import bcrypt
from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.enums import calculate_priority_score, get_priority_tier
from app.database.collections import Collections


def load_seed_json() -> Dict[str, Any]:
    """Loads extracted seed data JSON."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "data", "seed_data.json")
    if not os.path.exists(seed_path):
        raise FileNotFoundError(f"Seed data JSON not found at {seed_path}")
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_database(
    uri: Optional[str] = None,
    db_name: Optional[str] = None,
    force: bool = False,
    reset: bool = False,
) -> Dict[str, Any]:
    """
    Executes idempotent seeding of ProductMind AI demonstration data.
    
    Safety guards:
    - If database already contains data and force=False, exits without modifying.
    - If reset=True, drops collections before seeding (only for testing/isolated DBs).
    """
    mongo_uri = uri or settings.MONGODB_URI
    target_db = db_name or settings.DATABASE_NAME

    print("=" * 70)
    print("ProductMind AI - Python Database Seeder & Data Ingestion Layer")
    print(f"Target Database: {target_db}")
    print("=" * 70)

    client = MongoClient(mongo_uri)
    db = client[target_db]

    # Pre-check database state for safety
    existing_user_count = db[Collections.USERS].count_documents({})
    if existing_user_count > 0 and not force and not reset:
        client.close()
        raise RuntimeError(
            f"Database '{target_db}' is already populated ({existing_user_count} users found). "
            f"Aborting to prevent accidental data modification. Pass --force to update idempotently."
        )

    if reset:
        print(f"\n[Reset Mode] Clearing existing collections in '{target_db}'...")
        for col_name in db.list_collection_names():
            if not col_name.startswith("system."):
                db[col_name].drop()
        print("  All collections cleared.")

    seed_data = load_seed_json()
    initial_user = seed_data["initialUser"]
    initial_features = seed_data["initialFeatures"]
    initial_feedback = seed_data["initialFeedback"]
    initial_personas = seed_data["initialPersonas"]
    initial_prds = seed_data["initialPRDs"]
    initial_releases = seed_data["initialReleases"]
    initial_roadmap = seed_data["initialRoadmap"]
    initial_experiments = seed_data["initialExperiments"]
    initial_competitors = seed_data["initialCompetitors"]
    initial_journeys = seed_data["initialCustomerJourneys"]
    initial_scenarios = seed_data["initialScenarios"]

    # -------------------------------------------------------------------------
    # 1. Demo User
    # -------------------------------------------------------------------------
    normalized_email = (initial_user.get("email") or "alex.rivera@productmind.ai").lower().strip()
    pw_hash = bcrypt.hashpw(b"demo123", bcrypt.gensalt(10)).decode("utf-8")

    user_doc = db[Collections.USERS].find_one_and_update(
        {"email": normalized_email},
        {
            "$set": {
                "name": initial_user.get("name", "Alex Rivera"),
                "email": normalized_email,
                "passwordHash": pw_hash,
                "platformRole": "user",
                "avatar": initial_user.get("avatar"),
                "theme": initial_user.get("theme", "dark"),
                "reducedMotion": bool(initial_user.get("reducedMotion")),
                "isActive": True,
                "legacyId": initial_user.get("id", "usr-1"),
                "emailVerifiedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )
    user_id = user_doc["_id"]
    print(f"+ User verified: {user_doc['name']} ({user_doc['email']}) [ID: {user_id}]")

    # -------------------------------------------------------------------------
    # 2. Demo Workspace
    # -------------------------------------------------------------------------
    workspace_slug = "apex-saas-product-operations"
    workspace_doc = db[Collections.WORKSPACES].find_one_and_update(
        {"slug": workspace_slug},
        {
            "$set": {
                "name": initial_user.get("workspaceName", "Apex SaaS Product Operations"),
                "slug": workspace_slug,
                "ownerId": user_id,
                "plan": "Enterprise Tier",
                "legacyId": "ws-apex-01",
                "isArchived": False,
                "settings": {
                    "defaultTheme": "dark",
                    "reducedMotion": False,
                    "allowGuestViewers": True,
                },
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )
    workspace_id = workspace_doc["_id"]
    print(f"+ Workspace verified: {workspace_doc['name']} ({workspace_doc['slug']}) [ID: {workspace_id}]")

    # -------------------------------------------------------------------------
    # 3. Workspace Membership
    # -------------------------------------------------------------------------
    membership_doc = db[Collections.WORKSPACE_MEMBERSHIPS].find_one_and_update(
        {"workspaceId": workspace_id, "userId": user_id},
        {
            "$set": {
                "workspaceId": workspace_id,
                "userId": user_id,
                "role": initial_user.get("role", "Lead Product Architect"),
                "status": "active",
                "joinedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )
    print(f"+ Membership verified: {membership_doc['role']} (status: {membership_doc['status']})")

    # -------------------------------------------------------------------------
    # 4. Features (10 items)
    # -------------------------------------------------------------------------
    feature_map: Dict[str, ObjectId] = {}
    features_upserted = 0

    for feat in initial_features:
        f_id = feat["id"]
        impact = feat.get("customerImpact", 5)
        urgency = feat.get("urgency", 5)
        demand = feat.get("demand", 5)
        value = feat.get("businessValue", 5)
        
        calculated_score = calculate_priority_score(impact, urgency, demand, value)
        calculated_tier = get_priority_tier(calculated_score)

        comments = [
            {
                "author": c.get("author"),
                "text": c.get("text"),
                "createdAt": datetime.fromisoformat(c["createdAt"].replace("Z", "+00:00")) if c.get("createdAt") else datetime.now(timezone.utc),
            }
            for c in feat.get("comments", [])
        ]

        doc = db[Collections.FEATURES].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": f_id},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": f_id,
                    "name": feat["name"],
                    "description": feat.get("description", ""),
                    "customerImpact": impact,
                    "urgency": urgency,
                    "demand": demand,
                    "businessValue": value,
                    "score": calculated_score,
                    "priorityTier": calculated_tier,
                    "status": feat.get("status", "Backlog"),
                    "owner": feat.get("owner"),
                    "targetRelease": feat.get("targetRelease"),
                    "aiJustification": feat.get("aiJustification", ""),
                    "comments": comments,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
            return_document=True,
        )
        feature_map[f_id] = doc["_id"]
        features_upserted += 1

    print(f"+ Features processed: {features_upserted} items")

    # -------------------------------------------------------------------------
    # 5. Feature Groups (4 clusters)
    # -------------------------------------------------------------------------
    group_definitions = [
        {
            "legacyId": "grp-performance-latency",
            "title": "Performance Optimization: Data Grid Latency",
            "category": "Performance",
            "primaryTag": "latency",
            "description": "Customer requests for sub-16ms rendering and virtualization on large 5,000+ row feedback datasets.",
            "status": "approved",
            "promotedLegacyFeatureId": "feat-1",
            "painPoints": ["Slow dashboard loading (>5k items)", "Table stutter during triage filter queries"],
            "sentimentDistribution": {"Positive": 1, "Neutral": 1, "Negative": 1},
        },
        {
            "legacyId": "grp-integrations-jira-linear",
            "title": "Ecosystem Integrations: Bi-directional Jira & Linear Sync",
            "category": "Integrations",
            "primaryTag": "jira",
            "description": "Two-way synchronization for engineering handoff, PRD stories, and real-time status updates.",
            "status": "approved",
            "promotedLegacyFeatureId": "feat-2",
            "painPoints": ["Manual transcribing PRD stories into tickets", "Missing acceptance criteria during implementation"],
            "sentimentDistribution": {"Positive": 0, "Neutral": 2, "Negative": 0},
        },
        {
            "legacyId": "grp-usability-release-gating",
            "title": "Reliability & Governance: Quality Release Readiness Checklist",
            "category": "Reliability",
            "primaryTag": "release-readiness",
            "description": "Enforcing strict Go/No-Go quality gates, compliance checks, and security blockers before release.",
            "status": "approved",
            "promotedLegacyFeatureId": "feat-10",
            "painPoints": ["PMs accidentally marking releases ready with failed compliance", "No blocking gates on urgent bugs"],
            "sentimentDistribution": {"Positive": 0, "Neutral": 0, "Negative": 2},
        },
        {
            "legacyId": "grp-pricing-viewer-seats",
            "title": "Pricing & Licensing: Free Stakeholder Viewer Tier",
            "category": "Pricing",
            "primaryTag": "pricing",
            "description": "Transparent seat tiers for guest viewers across sales, marketing, and executives.",
            "status": "suggested",
            "promotedLegacyFeatureId": "feat-8",
            "painPoints": ["Pricing for small startups is steep", "Lack of clarity on viewer-only seat limits"],
            "sentimentDistribution": {"Positive": 0, "Neutral": 0, "Negative": 2},
        },
    ]

    group_map: Dict[str, ObjectId] = {}
    groups_upserted = 0

    for grp in group_definitions:
        promoted_feature_id = feature_map.get(grp["promotedLegacyFeatureId"]) if grp.get("promotedLegacyFeatureId") else None
        doc = db[Collections.FEATURE_GROUPS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": grp["legacyId"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": grp["legacyId"],
                    "title": grp["title"],
                    "category": grp["category"],
                    "primaryTag": grp["primaryTag"],
                    "description": grp["description"],
                    "status": grp["status"],
                    "painPoints": grp["painPoints"],
                    "sentimentDistribution": grp["sentimentDistribution"],
                    "promotedFeatureId": promoted_feature_id,
                    "feedbackCount": 0,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
            return_document=True,
        )
        group_map[grp["legacyId"]] = doc["_id"]
        groups_upserted += 1

        # Synchronize back-reference on Feature if promoted
        if promoted_feature_id:
            db[Collections.FEATURES].update_one(
                {"_id": promoted_feature_id},
                {"$set": {"featureGroupId": doc["_id"]}},
            )

    print(f"+ Feature Groups processed: {groups_upserted} items")

    # -------------------------------------------------------------------------
    # 6. Customer Feedback (20 items)
    # -------------------------------------------------------------------------
    feedback_upserted = 0
    group_counts: Dict[str, int] = {}

    for fb in initial_feedback:
        promoted_fid = feature_map.get(fb.get("linkedFeatureId")) if fb.get("linkedFeatureId") else None
        
        assigned_group_id = None
        linked_fid = fb.get("linkedFeatureId")
        cat = fb.get("category")
        if linked_fid == "feat-1" or cat == "Performance":
            assigned_group_id = group_map.get("grp-performance-latency")
        elif linked_fid == "feat-2" or cat == "Integrations":
            assigned_group_id = group_map.get("grp-integrations-jira-linear")
        elif linked_fid == "feat-10" or cat == "Reliability":
            assigned_group_id = group_map.get("grp-usability-release-gating")
        elif linked_fid == "feat-8" or cat == "Pricing":
            assigned_group_id = group_map.get("grp-pricing-viewer-seats")

        if assigned_group_id:
            str_gid = str(assigned_group_id)
            group_counts[str_gid] = group_counts.get(str_gid, 0) + 1

        fb_date = datetime.strptime(fb["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc) if fb.get("date") else datetime.now(timezone.utc)

        db[Collections.FEEDBACK_ITEMS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": fb["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": fb["id"],
                    "externalId": fb["id"],
                    "sourceType": "manual",
                    "title": fb["title"],
                    "description": fb.get("description", ""),
                    "customerName": fb.get("customer"),
                    "companyName": fb.get("company"),
                    "customerEmail": fb.get("email"),
                    "category": fb.get("category"),
                    "sentiment": fb.get("sentiment"),
                    "sourcePriority": fb.get("priority"),
                    "tags": fb.get("tags", []),
                    "sourceTags": fb.get("tags", []),
                    "feedbackDate": fb_date,
                    "featureGroupId": assigned_group_id,
                    "promotedFeatureId": promoted_fid,
                    "processingStatus": "processed",
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        feedback_upserted += 1

    # Update cached feedbackCount on feature groups
    for gid_str, count in group_counts.items():
        db[Collections.FEATURE_GROUPS].update_one(
            {"_id": ObjectId(gid_str)},
            {"$set": {"feedbackCount": count}},
        )

    print(f"+ Feedback items processed: {feedback_upserted} items")

    # -------------------------------------------------------------------------
    # 7. Customer Personas (4 items)
    # -------------------------------------------------------------------------
    personas_upserted = 0
    for p in initial_personas:
        db[Collections.CUSTOMER_PERSONAS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": p["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": p["id"],
                    "name": p["name"],
                    "role": p.get("role", ""),
                    "companyType": p.get("companyType"),
                    "avatar": p.get("avatar"),
                    "description": p.get("description", ""),
                    "goals": p.get("goals", []),
                    "frustrations": p.get("frustrations", []),
                    "needs": p.get("needs", []),
                    "featurePreferences": p.get("featurePreferences", []),
                    "sentimentSummary": p.get("sentimentSummary"),
                    "relatedFeedbackCount": p.get("relatedFeedbackCount", 0),
                    "isFavorite": bool(p.get("isFavorite")),
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        personas_upserted += 1

    print(f"+ Customer Personas processed: {personas_upserted} items")

    # -------------------------------------------------------------------------
    # 8. PRDs (2 items)
    # -------------------------------------------------------------------------
    prds_upserted = 0
    for prd in initial_prds:
        linked_fid = feature_map.get(prd.get("featureId")) if prd.get("featureId") else None
        db[Collections.PRDS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": prd["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": prd["id"],
                    "title": prd["title"],
                    "version": prd.get("version", "1.0.0"),
                    "status": prd.get("status", "Draft"),
                    "author": prd.get("author"),
                    "featureId": linked_fid,
                    "sections": prd.get("sections", {}),
                    "aiGenerated": False,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        prds_upserted += 1

    print(f"+ PRDs processed: {prds_upserted} items")

    # -------------------------------------------------------------------------
    # 9. Releases (2 items)
    # -------------------------------------------------------------------------
    release_map: Dict[str, ObjectId] = {}
    releases_upserted = 0

    for rel in initial_releases:
        resolved_fids = [feature_map[fid] for fid in rel.get("includedFeatureIds", []) if fid in feature_map]
        checklist = [
            {
                "title": c["title"],
                "completed": bool(c.get("completed")),
                "required": bool(c.get("required")),
            }
            for c in rel.get("checklist", [])
        ]
        doc = db[Collections.RELEASES].find_one_and_update(
            {"workspaceId": workspace_id, "version": rel["version"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": rel["id"],
                    "name": rel["name"],
                    "version": rel["version"],
                    "description": rel.get("description", ""),
                    "plannedDate": rel.get("plannedDate"),
                    "owner": rel.get("owner"),
                    "status": rel.get("status", "In Progress"),
                    "includedFeatureIds": resolved_fids,
                    "checklist": checklist,
                    "releaseNotes": rel.get("releaseNotes", ""),
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
            return_document=True,
        )
        release_map[rel["id"]] = doc["_id"]
        releases_upserted += 1

    print(f"+ Releases processed: {releases_upserted} items")

    # -------------------------------------------------------------------------
    # 10. Roadmap Items (8 items)
    # -------------------------------------------------------------------------
    roadmap_map: Dict[str, ObjectId] = {}
    roadmap_upserted = 0

    for rd in initial_roadmap:
        linked_fid = feature_map.get(rd.get("featureId")) if rd.get("featureId") else None
        target_rel_id = None
        if rd["id"] in ["rd-1", "rd-2", "rd-4", "rd-6"]:
            target_rel_id = release_map.get("rel-1")
        elif rd["id"] in ["rd-5", "rd-8"]:
            target_rel_id = release_map.get("rel-2")

        doc = db[Collections.ROADMAP_ITEMS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": rd["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": rd["id"],
                    "title": rd["title"],
                    "description": rd.get("description", ""),
                    "featureId": linked_fid,
                    "releaseId": target_rel_id,
                    "status": rd.get("status", "Planned"),
                    "priority": rd.get("priority", "Medium"),
                    "owner": rd.get("owner"),
                    "startDate": rd.get("startDate"),
                    "targetDate": rd.get("targetDate"),
                    "milestone": rd.get("milestone"),
                    "progress": rd.get("progress", 0),
                    "notes": rd.get("notes", ""),
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
            return_document=True,
        )
        roadmap_map[rd["id"]] = doc["_id"]
        roadmap_upserted += 1

    # Resolve dependencies & link release roadmapItemIds
    for rd in initial_roadmap:
        resolved_deps = [roadmap_map[dep_id] for dep_id in rd.get("dependencies", []) if dep_id in roadmap_map]
        if resolved_deps:
            db[Collections.ROADMAP_ITEMS].update_one(
                {"workspaceId": workspace_id, "legacyId": rd["id"]},
                {"$set": {"dependencies": resolved_deps}},
            )

    if "rel-1" in release_map:
        r1_items = [roadmap_map[i] for i in ["rd-1", "rd-2", "rd-4", "rd-6"] if i in roadmap_map]
        db[Collections.RELEASES].update_one({"_id": release_map["rel-1"]}, {"$set": {"roadmapItemIds": r1_items}})

    if "rel-2" in release_map:
        r2_items = [roadmap_map[i] for i in ["rd-5", "rd-8"] if i in roadmap_map]
        db[Collections.RELEASES].update_one({"_id": release_map["rel-2"]}, {"$set": {"roadmapItemIds": r2_items}})

    print(f"+ Roadmap Items processed: {roadmap_upserted} items")

    # -------------------------------------------------------------------------
    # 11. Product Experiments (3 items)
    # -------------------------------------------------------------------------
    experiments_upserted = 0
    for exp in initial_experiments:
        linked_fid = feature_map.get(exp.get("linkedFeatureId")) if exp.get("linkedFeatureId") else None
        db[Collections.PRODUCT_EXPERIMENTS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": exp["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": exp["id"],
                    "name": exp["name"],
                    "problem": exp.get("problem", ""),
                    "hypothesis": exp["hypothesis"],
                    "targetAudience": exp.get("targetAudience", "All active users"),
                    "proposedChange": exp.get("proposedChange", ""),
                    "successMetric": exp["successMetric"],
                    "baseline": exp.get("baseline", 0),
                    "target": exp.get("target", 0),
                    "observedValue": exp.get("observedValue"),
                    "startDate": exp.get("startDate"),
                    "endDate": exp.get("endDate"),
                    "linkedFeatureId": linked_fid,
                    "owner": exp.get("owner"),
                    "status": exp.get("status", "Running"),
                    "conclusion": exp.get("conclusion", "Continue"),
                    "notes": exp.get("notes", ""),
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        experiments_upserted += 1

    print(f"+ Product Experiments processed: {experiments_upserted} items")

    # -------------------------------------------------------------------------
    # 12. Competitor Intel (3 items)
    # -------------------------------------------------------------------------
    competitors_upserted = 0
    for comp in initial_competitors:
        last_rev = datetime.strptime(comp["lastReviewed"], "%Y-%m-%d").replace(tzinfo=timezone.utc) if comp.get("lastReviewed") else datetime.now(timezone.utc)
        db[Collections.COMPETITOR_INTEL].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": comp["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": comp["id"],
                    "name": comp["name"],
                    "productDescription": comp.get("productDescription", ""),
                    "website": comp.get("website", ""),
                    "targetAudience": comp.get("targetAudience"),
                    "keyFeatures": comp.get("keyFeatures", []),
                    "strengths": comp.get("strengths", []),
                    "weaknesses": comp.get("weaknesses", []),
                    "differentiators": comp.get("differentiators", []),
                    "researchNotes": comp.get("researchNotes", ""),
                    "lastReviewed": last_rev,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        competitors_upserted += 1

    print(f"+ Competitor Intel processed: {competitors_upserted} items")

    # -------------------------------------------------------------------------
    # 13. Customer Journeys (5 stages)
    # -------------------------------------------------------------------------
    journeys_upserted = 0
    for stage in initial_journeys:
        touchpoints = [
            {
                "name": tp["name"],
                "sentiment": tp.get("sentiment", "Positive"),
                "painPoints": tp.get("painPoints", ""),
                "opportunity": tp.get("opportunity", ""),
            }
            for tp in stage.get("touchpoints", [])
        ]
        db[Collections.CUSTOMER_JOURNEYS].find_one_and_update(
            {"workspaceId": workspace_id, "order": stage["order"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": stage["id"],
                    "name": stage["name"],
                    "order": stage["order"],
                    "description": stage.get("description", ""),
                    "touchpoints": touchpoints,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        journeys_upserted += 1

    print(f"+ Customer Journeys processed: {journeys_upserted} stages")

    # -------------------------------------------------------------------------
    # 14. Prioritization Scenarios (1 item)
    # -------------------------------------------------------------------------
    scenarios_upserted = 0
    for scen in initial_scenarios:
        adj_features = [
            {
                "featureId": feature_map.get(item["featureId"]) or ObjectId(),
                "customerImpact": item.get("customerImpact", 5),
                "urgency": item.get("urgency", 5),
                "demand": item.get("demand", 5),
                "businessValue": item.get("businessValue", 5),
            }
            for item in scen.get("adjustedFeatures", [])
        ]
        db[Collections.PRIORITIZATION_SCENARIOS].find_one_and_update(
            {"workspaceId": workspace_id, "legacyId": scen["id"]},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "legacyId": scen["id"],
                    "name": scen["name"],
                    "description": scen.get("description", ""),
                    "createdBy": user_id,
                    "adjustedFeatures": adj_features,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        scenarios_upserted += 1

    print(f"+ Prioritization Scenarios processed: {scenarios_upserted} items")

    # -------------------------------------------------------------------------
    # 15. Copilot Conversation & Messages (1 conversation + 1 message)
    # -------------------------------------------------------------------------
    chat_doc = db[Collections.COPILOT_CONVERSATIONS].find_one_and_update(
        {"workspaceId": workspace_id, "legacyId": "chat-1"},
        {
            "$set": {
                "workspaceId": workspace_id,
                "userId": user_id,
                "legacyId": "chat-1",
                "title": "Initial Product Strategy Discussion",
                "isArchived": False,
                "lastMessageAt": datetime.now(timezone.utc),
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
        return_document=True,
    )
    chat_id = chat_doc["_id"]

    db[Collections.COPILOT_MESSAGES].find_one_and_update(
        {"conversationId": chat_id, "legacyId": "msg-seed-1"},
        {
            "$set": {
                "workspaceId": workspace_id,
                "conversationId": chat_id,
                "legacyId": "msg-seed-1",
                "role": "assistant",
                "content": (
                    "Hello! I am your **Product Mind AI Copilot**. I analyze your customer feedback, "
                    "calculate algorithmic priority scores, and synthesize roadmap recommendations in real time. "
                    "How can I help you today?"
                ),
                "modelInfo": {
                    "provider": "google",
                    "modelName": "gemini-1.5-pro",
                    "tokensUsed": 42,
                },
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    print(f"+ Copilot Session initialized: conversation ID [{chat_id}]")

    # -------------------------------------------------------------------------
    # 16. Analytics Daily Rollups (14 days)
    # -------------------------------------------------------------------------
    dates = [
        "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
        "2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14",
        "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18",
    ]
    rollups_upserted = 0
    for i, d in enumerate(dates):
        base_active = 38 + i
        base_events = 520 + i * 22
        base_sessions = 85 + i * 4

        feature_metrics = [
            {
                "name": "PRD Generator",
                "eventCount": round(base_events * 0.42),
                "uniqueUsers": round(base_active * 0.85),
                "adoptionPercent": 85,
                "avgDurationSec": 210,
                "completionRate": 88,
            },
            {
                "name": "Feedback Explorer",
                "eventCount": round(base_events * 0.32),
                "uniqueUsers": round(base_active * 0.78),
                "adoptionPercent": 78,
                "avgDurationSec": 140,
                "completionRate": 92,
            },
            {
                "name": "What-If Simulator",
                "eventCount": round(base_events * 0.26),
                "uniqueUsers": round(base_active * 0.65),
                "adoptionPercent": 65,
                "avgDurationSec": 165,
                "completionRate": 74,
            },
        ]

        funnel_metrics = [
            {"step": "1. Visit Workspace", "users": base_active, "conversionRate": 100, "dropOffRate": 0},
            {"step": "2. Review Feedback", "users": round(base_active * 0.9), "conversionRate": 90, "dropOffRate": 10},
            {"step": "3. Triage & Prioritize", "users": round(base_active * 0.75), "conversionRate": 75, "dropOffRate": 15},
            {"step": "4. Draft PRD Specs", "users": round(base_active * 0.58), "conversionRate": 58, "dropOffRate": 17},
            {"step": "5. Release Quality Gate", "users": round(base_active * 0.42), "conversionRate": 42, "dropOffRate": 16},
        ]

        db[Collections.ANALYTICS_DAILY_ROLLUPS].find_one_and_update(
            {"workspaceId": workspace_id, "date": d},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "date": d,
                    "activeUsers": base_active,
                    "totalSessions": base_sessions,
                    "totalEvents": base_events,
                    "avgSessionDuration": 195 + (i % 5) * 10,
                    "topFeature": "PRD Generator",
                    "featureMetrics": feature_metrics,
                    "funnelMetrics": funnel_metrics,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        rollups_upserted += 1

    print(f"+ Analytics Daily Rollups processed: {rollups_upserted} days")

    # -------------------------------------------------------------------------
    # 17. Sample Raw Analytics Events (20 items)
    # -------------------------------------------------------------------------
    raw_events_upserted = 0
    for i in range(20):
        evt_id = f"evt-seed-20261018-{i + 1}"
        feat_name = "PRD Generator" if i % 3 == 0 else ("Feedback Explorer" if i % 3 == 1 else "What-If Simulator")
        db[Collections.ANALYTICS_EVENTS].find_one_and_update(
            {"workspaceId": workspace_id, "eventId": evt_id},
            {
                "$set": {
                    "workspaceId": workspace_id,
                    "eventId": evt_id,
                    "eventName": "view_page" if i % 2 == 0 else "click_action",
                    "eventType": "telemetry",
                    "eventTimestamp": datetime.now(timezone.utc) - timedelta(hours=i),
                    "date": "2026-10-18",
                    "actorId": f"usr-actor-{(i % 5) + 1}",
                    "sessionId": f"sess-{int(i / 3) + 1}",
                    "featureName": feat_name,
                    "durationSeconds": (i + 1) * 15,
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        raw_events_upserted += 1

    print(f"+ Analytics Raw Events processed: {raw_events_upserted} items")

    # -------------------------------------------------------------------------
    # 18. Audit Log Entry (Idempotent by workspaceId & action)
    # -------------------------------------------------------------------------
    db[Collections.AUDIT_LOGS].find_one_and_update(
        {
            "workspaceId": workspace_id,
            "action": "created",
            "entityType": "workspace",
            "entityId": str(workspace_id),
        },
        {
            "$set": {
                "workspaceId": workspace_id,
                "actor": user_doc["name"],
                "userId": user_id,
                "entityType": "workspace",
                "entityId": str(workspace_id),
                "action": "created",
                "description": "Initialized ProductMind AI demonstration workspace and seeded baseline product intelligence.",
                "canUndo": False,
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    print("+ Seed Audit Log record created.\n")

    # -------------------------------------------------------------------------
    # Verification & Document Counts
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("Database Verification - Seed Document Counts")
    print("=" * 70)

    expected_counts = {
        Collections.USERS: 1,
        Collections.WORKSPACES: 1,
        Collections.WORKSPACE_MEMBERSHIPS: 1,
        Collections.FEATURES: 10,
        Collections.FEATURE_GROUPS: 4,
        Collections.FEEDBACK_ITEMS: 20,
        Collections.CUSTOMER_PERSONAS: 4,
        Collections.PRDS: 2,
        Collections.RELEASES: 2,
        Collections.ROADMAP_ITEMS: 8,
        Collections.PRODUCT_EXPERIMENTS: 3,
        Collections.COMPETITOR_INTEL: 3,
        Collections.CUSTOMER_JOURNEYS: 5,
        Collections.PRIORITIZATION_SCENARIOS: 1,
        Collections.COPILOT_CONVERSATIONS: 1,
        Collections.COPILOT_MESSAGES: 1,
        Collections.ANALYTICS_DAILY_ROLLUPS: 14,
        Collections.ANALYTICS_EVENTS: 20,
        Collections.AUDIT_LOGS: 1,
    }

    verification_results = {}
    all_passed = True
    total_docs = 0

    for col_name, expected in expected_counts.items():
        actual = db[col_name].count_documents({})
        total_docs += actual
        is_pass = actual >= expected
        if not is_pass:
            all_passed = False
        verification_results[col_name] = {"expected": expected, "actual": actual, "pass": is_pass}
        print(f"{col_name:<26} | Expected: {expected:<2} | Actual in DB: {actual:<2} | [{'PASS' if is_pass else 'FAIL'}]")

    print("-" * 70)
    print(f"Total verified documents: {total_docs}")
    print("=" * 70)
    print("ALL COLLECTIONS SEEDED AND VERIFIED SUCCESSFULLY" if all_passed else "SOME COUNTS FAILED")
    print("=" * 70)

    client.close()
    return {
        "success": all_passed,
        "total_documents": total_docs,
        "results": verification_results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed ProductMind AI demonstration data into MongoDB.")
    parser.add_argument("--force", action="store_true", help="Allow updating existing populated database.")
    parser.add_argument("--reset", action="store_true", help="Drop collections before seeding.")
    parser.add_argument("--db-name", type=str, default=None, help="Target database name override.")
    parser.add_argument("--uri", type=str, default=None, help="MongoDB connection URI override.")
    args = parser.parse_args()

    try:
        res = seed_database(uri=args.uri, db_name=args.db_name, force=args.force, reset=args.reset)
        sys.exit(0 if res["success"] else 1)
    except Exception as e:
        print(f"\n[Error] Seeder failed: {e}")
        sys.exit(1)
