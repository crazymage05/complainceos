import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# MongoDB Atlas MCP Server integration
# MCP config: see mcp_config.json
# Connection via pymongo/motor using MONGODB_URI env var

_client: AsyncIOMotorClient = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI", "")
        _client = AsyncIOMotorClient(uri)
    return _client

def get_db() -> AsyncIOMotorDatabase:
    client = get_client()
    return client[os.getenv("MONGODB_DB_NAME", "complianceos")]

async def create_indexes(db: AsyncIOMotorDatabase):
    await db.businesses.create_index("owner")
    await db.obligation_instances.create_index([("business_id", 1), ("status", 1)])
    await db.obligation_instances.create_index([("business_id", 1), ("decay_score", 1)])
    await db.regulatory_corpus.create_index([("category", 1)])
    await db.regulatory_corpus.create_index([("applicable_to.industries", 1)])
    await db.regulatory_changes.create_index([("effective_date", -1)])
    await db.agent_decisions.create_index([("business_id", 1), ("timestamp", -1)])
    await db.filing_history.create_index([("business_id", 1), ("regulation_id", 1)])
