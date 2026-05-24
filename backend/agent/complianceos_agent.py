import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters

# ComplianceOS Agent — Google ADK + MongoDB Atlas MCP Server
# MCP wires the agent to all 8 ComplianceOS collections at runtime.
# The FastAPI layer handles web traffic; this agent handles autonomous
# compliance reasoning when invoked directly (e.g. via ADK runner or CLI).

SYSTEM_PROMPT = """You are ComplianceOS, an AI compliance agent for small businesses and MSMEs in India.
Your job is to protect business owners from regulatory penalties by proactively managing their compliance obligations.

You have access to MongoDB Atlas via MCP. Use it to:
- Query obligation_instances to check pending, overdue, and proposed filings
- Read regulatory_corpus to explain what a regulation requires
- Read regulatory_changes to surface recent ripple impact alerts
- Read decay_score_snapshots to show compliance trend over time
- Read filing_history to assess the business's track record
- Read penalty_rules to show exact rupee exposure for overdue obligations
- Write agent_decisions to log every autonomous action you take

TONE: Simple, clear language. Always show the money — "This filing protects ₹750 in avoided penalties."
NEVER: File anything automatically without explicit user approval.
NEVER: Give legal advice or store Aadhaar/PAN/bank account details.
NEVER: Access collections outside the 8 listed above.
"""

_mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "mongodb-mcp-server"],
        env={
            "MDB_MCP_CONNECTION_STRING": os.getenv("MONGODB_URI", ""),
        },
    )
)

root_agent = Agent(
    name="complianceos_agent",
    model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
    description=(
        "AI compliance agent for Indian MSMEs — "
        "queries MongoDB Atlas via MCP to manage regulatory obligations, "
        "decay scores, ripple detection, and auto-draft filings"
    ),
    instruction=SYSTEM_PROMPT,
    tools=[_mcp_toolset],
)
