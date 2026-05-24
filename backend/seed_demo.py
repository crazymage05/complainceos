"""
Pre-seed demo chat_discoveries and obligation_instances for a business.

Usage:
  python seed_demo.py --business-id <MONGO_OBJECT_ID>

This makes the AI Advisor tab open with 5 pre-discovered obligations already
visible, so the demo doesn't spend 40 seconds on API calls before showing value.
"""
import argparse
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DEMO_OBLIGATIONS = [
    {
        "obligation_name": "TCS Collection under Section 9(5) — Swiggy/Zomato",
        "reason": "You supply restaurant services through an ECO. The ECO collects TCS at 1% — you must provide GSTIN to each platform.",
        "category": "taxation",
        "urgency": "immediate",
        "frequency": "monthly",
        "max_penalty_inr": 50000,
        "days_until_due": 15,
    },
    {
        "obligation_name": "EPF Enrollment — Employees Crossing ₹21,000 Wage Ceiling",
        "reason": "EPFO enhanced wage ceiling to ₹21,000/month effective April 2024. All employees below this must be enrolled.",
        "category": "labour",
        "urgency": "next_30_days",
        "frequency": "monthly",
        "max_penalty_inr": 25000,
        "days_until_due": 25,
    },
    {
        "obligation_name": "FSSAI Annual Return — Form D-1 on FoSCoS Portal",
        "reason": "As a food business operator, you must file Form D-1 annually. Deadline: 31 May 2025. Late penalty ₹100/day.",
        "category": "food_safety",
        "urgency": "next_30_days",
        "frequency": "annual",
        "max_penalty_inr": 5000,
        "days_until_due": 7,
    },
    {
        "obligation_name": "POSH Policy and ICC Constitution",
        "reason": "Businesses with 10+ employees must constitute an Internal Complaints Committee under POSH Act, 2013.",
        "category": "labour",
        "urgency": "annual",
        "frequency": "annual",
        "max_penalty_inr": 50000,
        "days_until_due": 60,
    },
    {
        "obligation_name": "Fire NOC Renewal — Premises Licence",
        "reason": "Food businesses with a commercial kitchen require a valid Fire NOC from the state Fire Department, typically renewed annually.",
        "category": "fire_safety",
        "urgency": "annual",
        "frequency": "annual",
        "max_penalty_inr": 10000,
        "days_until_due": 75,
    },
]


def seed(business_id: str):
    uri = os.getenv("MONGODB_URI", "")
    db_name = os.getenv("MONGODB_DB_NAME", "complianceos")
    client = MongoClient(uri)
    db = client[db_name]

    now = datetime.utcnow()

    # Clear existing demo data for this business to avoid duplicates
    db.chat_discoveries.delete_many({"business_id": business_id, "source": "demo_seed"})

    inserted_disc = 0
    inserted_inst = 0

    for obl in DEMO_OBLIGATIONS:
        # Insert chat_discovery
        db.chat_discoveries.insert_one({
            "business_id": business_id,
            "obligation_name": obl["obligation_name"],
            "reason": obl["reason"],
            "category": obl["category"],
            "urgency": obl["urgency"],
            "source": "demo_seed",
            "discovered_at": now - timedelta(hours=inserted_disc),  # stagger timestamps
        })
        inserted_disc += 1

        # Insert obligation_instance if one with a similar name doesn't exist
        name_prefix = obl["obligation_name"][:20]
        existing = db.obligation_instances.find_one({
            "business_id": business_id,
            "name": {"$regex": f"^{name_prefix[:15]}", "$options": "i"},
        })
        if not existing:
            due_date = now + timedelta(days=obl["days_until_due"])
            db.obligation_instances.insert_one({
                "business_id": business_id,
                "regulation_id": f"demo_{obl['category']}_{inserted_inst}",
                "name": obl["obligation_name"],
                "category": obl["category"],
                "frequency": obl["frequency"],
                "deadline_rule": obl["reason"],
                "penalty_type": "fixed",
                "max_penalty_inr": obl["max_penalty_inr"],
                "complexity": 2,
                "depends_on": [],
                "imprisonment_risk": False,
                "status": "pending",
                "source": "ai_advisor",
                "decay_score": None,
                "due_date": due_date,
                "created_at": now,
            })
            inserted_inst += 1

    print(f"Seeded {inserted_disc} discoveries and {inserted_inst} obligation instances for business {business_id}")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-id", required=True, help="MongoDB ObjectId of the demo business")
    args = parser.parse_args()
    seed(args.business_id)
