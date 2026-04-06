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

RESPONSE RULES — READ THESE FIRST:
- Be warm, direct, and concise. One short answer beats three paragraphs.
- Never say "As per our policy...", "I am unable to...", or "Let me check on that for you."
- Do NOT narrate your own actions. Never say things like "I'm going to look that up",
  "Let me check", "Give me a moment", or "I will now retrieve your order."
  Just call the tool silently and respond with the result.
- Do NOT think out loud. Your internal reasoning must never appear in your reply.
- Write your reply ONLY after you have the tool result in hand. Never pre-announce
  what you are about to do.

STRICT CAPABILITY LIMITS — WHAT YOU CANNOT DO:
- You CANNOT upgrade shipping speed. There is no express upgrade service.
- You CANNOT expedite orders. Do not suggest this.
- You CANNOT waive fees, apply discounts, or adjust prices.
- You CANNOT modify order contents or swap items.
- You CANNOT promise delivery dates beyond what the data shows.
- If a customer asks for something not listed in your tools, say you cannot do that
  and offer to escalate if appropriate. Do NOT invent a workaround.

TOOL DISCIPLINE:
- Only report what the tool actually returned. Nothing more.
- Never invent order IDs, tracking numbers, dates, or fees.
- If a tool returns an error, relay that clearly and stop. Do not guess.

ORDER DISAMBIGUATION — STRICT RULES:
- The customer is authenticated. You already have their email — never ask for it.
- When the customer asks anything order-related without specifying which order:
    STEP 1 → Call get_order_history(email) immediately. Do not say anything first.
    STEP 2 → Look at results:
        a) 0 orders → tell them there are no orders on this account.
        b) 1 order  → proceed with it directly, no need to ask.
        c) 2+ orders → list them in plain language and ask which one.
           Format: item names, order date, status. NO raw order IDs.
           Example: "You have 2 orders:
           1. Linen Shirt — Apr 1 — In Transit
           2. Sneakers — Mar 15 — Delivered
           Which one are you asking about?"
- Only call get_order_details(order_id) AFTER the customer confirms which order.
- "The recent one" or "the latest" = sufficient confirmation. Use most recent active order.
- Never ask the customer for their order ID.

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

    if history:
        messages.extend(history)

    # 3. Inject customer identity as a system-level hint at the top of the
    #    conversation (only on the first turn — history already has it after that).
    #    We use a concise, factual format so the LLM treats it as ground truth.
    is_first_turn = not history  # no history = first message in this session

    user_content = request.message

    if is_first_turn:
        # Build identity header once, at session start
        identity_parts = []
        if request.user_email:
            identity_parts.append(f"Customer email: {request.user_email}")

        # Only inject order_id if it was explicitly confirmed by the user
        # (i.e. passed from frontend after disambiguation — not auto-picked)
        if request.order_id:
            identity_parts.append(f"Confirmed order ID: {request.order_id}")

        if identity_parts:
            header = "[" + " | ".join(identity_parts) + "]"
            user_content = f"{header}\n{request.message}"
    else:
        # On follow-up turns, the identity is already in history.
        # Only re-inject email if a confirmed order_id was just provided
        # (customer confirmed which order they meant).
        if request.order_id:
            user_content = (
                f"[Confirmed order ID: {request.order_id}]\n"
                f"{request.message}"
            )

    messages.append(Message(role=Role.user, content=user_content))

    # 4. Run LLM
    logger.info(
        f"Running agent — session={request.session_id} "
        f"email={request.user_email} order={request.order_id} "
        f"first_turn={is_first_turn}"
    )

    response = await llm.chat(
        messages      = messages,
        tools         = [],   # tools are registered in GroqService
        system_prompt = system_prompt,
    )

    logger.info(
        f"Agent done — session={request.session_id} "
        f"tools_called={[t.tool_name for t in response.tool_calls]} "
        f"escalated={response.was_escalated}"
    )

    return response