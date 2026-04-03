# backend/agent/loop.py

import logging
from backend.agent.schemas import AgentResponse, ChatRequest, Message, Role
from backend.services.llm_base import LLMBase
from backend.policies.file_store import FilePolicyStore
from backend.tools.base import BaseTool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """
You are a customer support agent for Leafy, a D2C e-commerce brand.
You help customers with questions about their orders, returns, shipping,
payments, loyalty points, and account issues.

RULES:
- Always be warm, direct, and helpful. Never robotic.
- Use the tools available to look up real data before answering order-specific questions.
- Never guess order details — always look them up.
- If you cannot resolve an issue, follow the escalation guidelines in the context below.
- Keep responses concise. One clear answer beats three paragraphs.
- Never say "As per our policy..." or "I am unable to...".

TOOL RESPONSE DISCIPLINE:
- When a tool returns a result, communicate exactly what it says — nothing more.
- Do NOT add suggestions, next steps, or alternative options that the tool did not return.
- Do NOT add caveats or warnings that don't apply to the current situation (e.g. don't
  warn about shipping cutoffs after already confirming an address was updated).
- If a tool rejects a request, relay that outcome clearly and stop. Do not invent
  workarounds or offer alternatives unless the tool explicitly provides them.
- For order history, summarize — do not list every order in full detail. Give the customer
  a clear overview (how many orders, recent statuses) and offer to dig into any specific one.

KNOWLEDGE CONTEXT:
{knowledge_context}
""".strip()


async def run_agent(
    request:      ChatRequest,
    llm:          LLMBase,
    policy_store: FilePolicyStore,
    history:      list[Message] | None = None,
) -> AgentResponse:
    """
    Single entry point for running the agent.

    Args:
        request:      The incoming chat request
        llm:          GroqService instance (injected)
        policy_store: FilePolicyStore instance (injected)
        history:      Previous messages in this session (optional)

    Returns:
        AgentResponse with the final reply
    """

    # 1. Build knowledge context from user message
    knowledge_context = policy_store.build_context(request.message)
    system_prompt     = SYSTEM_PROMPT_TEMPLATE.format(
        knowledge_context=knowledge_context
    )

    # 2. Build message history
    messages: list[Message] = []

    # Inject prior history if provided
    if history:
        messages.extend(history)

    # Add context hints if customer provided email or order_id
    user_content = request.message
    if request.user_email and request.order_id:
        user_content = (
            f"[Customer email: {request.user_email} | Order ID: {request.order_id}]\n"
            f"{request.message}"
        )
    elif request.user_email:
        user_content = (
            f"[Customer email: {request.user_email}]\n"
            f"{request.message}"
        )
    elif request.order_id:
        user_content = (
            f"[Order ID: {request.order_id}]\n"
            f"{request.message}"
        )

    messages.append(Message(role=Role.user, content=user_content))

    # 3. Run LLM
    logger.info(
        f"Running agent — session={request.session_id} "
        f"email={request.user_email} order={request.order_id}"
    )

    response = await llm.chat(
        messages      = messages,
        tools         = [],   # tools are already registered in GroqService
        system_prompt = system_prompt,
    )

    logger.info(
        f"Agent done — session={request.session_id} "
        f"tools_called={[t.tool_name for t in response.tool_calls]} "
        f"escalated={response.was_escalated}"
    )

    return response