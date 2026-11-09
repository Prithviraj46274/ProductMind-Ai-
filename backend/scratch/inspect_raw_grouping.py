"""
Minimal diagnostic: call Groq Qwen directly and print the raw JSON response
for a feature grouping prompt with 3 clearly identical feature requests.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend")
from dotenv import load_dotenv
load_dotenv(r"c:\Users\vinay\OneDrive\Documents\ProductMind-Ai-\backend\.env")

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.ai.config import ai_settings

async def inspect():
    settings = ai_settings
    
    # Call WITHOUT structured output to see raw model response
    client = ChatGroq(
        model=settings.AI_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=0.1,
        max_tokens=4096,
        reasoning_format="hidden",
    )

    system_msg = SystemMessage(content="""You are a Feature Intelligence agent. Analyze customer feature requests and group semantically equivalent ones.

Output JSON with this exact schema:
{
  "groups": [
    {
      "group_name": "string",
      "feature_summary": "string (1-2 sentences)",
      "consolidated_description": "string (detailed synthesis)",
      "related_feedback_ids": ["id1", "id2"],
      "common_themes": ["tag1"],
      "common_pain_points": ["pain1"],
      "evidence": ["exact quote from feedback"],
      "suggested_capability": "string",
      "grouping_confidence": 0.95,
      "grouping_reason": "string explaining why these belong together"
    }
  ],
  "ungrouped_feedback_ids": [],
  "overall_reasoning": "string"
}

Rules:
- Group requests expressing the SAME capability together.
- Every related_feedback_ids entry MUST be an exact ID from the input.
- Minimum confidence: 0.5
- Minimum group size: 1
""")

    human_msg = HumanMessage(content="""Analyze these 3 customer feature requests and group them:

--- Candidate #1 ---
Feedback ID: fb_001
Title: Automated CSV and Excel scheduled export for compliance audits
Description: We urgently require automated recurring CSV and Excel export functionality for our monthly financial compliance audits. Analysts spend 3 hours weekly manually dumping tables.
Sentiment: Negative | Urgency: High
Customer: Finance Director @ AcquiredCorp

--- Candidate #2 ---
Feedback ID: fb_002
Title: One-click CSV data export button on reporting tables
Description: Please add a one-click CSV export button on reporting tables. Copy-pasting metrics manually is creating severe friction for our 20 analysts.
Sentiment: Negative | Urgency: High
Customer: Operations Lead @ Apex Retail

--- Candidate #3 ---
Feedback ID: fb_003
Title: Scheduled recurring CSV export automation for audit reporting
Description: Need ability to schedule recurring CSV table report exports so our team can automate weekly data compliance audits without manual exports.
Sentiment: Neutral | Urgency: High
Customer: Head of Analytics @ NovaScale

Generate the structured feature grouping analysis. Return ONLY valid JSON.""")

    print("Invoking Groq Qwen (unstructured)...")
    result = await client.ainvoke([system_msg, human_msg])
    print("RAW CONTENT:")
    print(result.content)
    print("\nUSAGE:", getattr(result, "usage_metadata", None))

if __name__ == "__main__":
    asyncio.run(inspect())
