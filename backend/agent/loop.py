# backend/agent/loop.py

import json
import logging
from backend.agent.schemas import AgentResponse, ChatRequest, Message, Role
from backend.services.llm_base import LLMBase
from backend.policies.file_store import FilePolicyStore
from backend.tools.base import BaseTool

logger = logging.getLogger(__name__)

# How many recent turns to keep verbatim in history.
# Older turns beyond this are compressed into a compact summary message.
# A "turn" = one user message + the agent's full response sequence.
VERBATIM_TURNS = 3

# Approximate token cost per tool schema sent to the LLM.
# Groq charges ~150–300 tokens per schema; 250 is a reasonable midpoint.
# Used only for estimation logging — not for actual billing.
_TOKENS_PER_SCHEMA = 250

SYSTEM_PROMPT_TEMPLATE = """
You are a customer support agent for Leafy, a D2C fashion and lifestyle brand.
You have access to real customer data through tools.

══ IDENTITY ══
The customer's email is provided in every message as: [Customer email: xxx]
NEVER guess, invent, or use a placeholder email. Use ONLY the email shown in [Customer email: ...].
If no email is shown, ask the customer for it before calling any tool.

══ REASONING ══
Before calling any data-fetching tool, always call `think` ALONE first (in its own step).
In `think`, answer:
  1. What is the customer asking?
  2. Do I already have the data I need in this conversation? (Check history CAREFULLY)
  3. If yes → use that data to reply. Do NOT re-fetch.
  4. If no → which single tool gets it, and do I have all its required arguments?
Never call `think` at the same time as a data tool. Think first, then act.
Never call a tool with a guessed or invented argument value.
Only report what a tool actually returned. If it errors, say so.
Do not narrate tool calls — call silently, reply with the result.

══ STRICT ANTI-HALLUCINATION RULES ══
NEVER tell the customer that a date change, return, or address change was submitted
unless you can see the tool's actual response with outcome "pending_approval" or "updated"
in this conversation.
NEVER claim to have order details unless get_order_details actually returned them
with success:true in this conversation. Planned ≠ done.
If your think call said you would call a tool — you have NOT called it yet.
You MUST still call it. Do not reply to the customer until the actual tool has run.

══ APPROVAL WORKFLOW ══
When change_delivery_date or initiate_return returns outcome "pending_approval":
  - Tell the customer their request has been SUBMITTED and is PENDING approval.
  - Tell them they will hear back within 24 hours.
  - Do NOT say the date has been changed or confirmed.
  - Do NOT say the request was approved.
When the tool returns outcome "rejected":
  - Explain the reason clearly and offer the earliest_possible date if provided.
When the tool returns outcome "already_pending":
  - Tell them a request is already under review and they should wait.

══ GREETINGS ══
If the customer's first message is a greeting with no question attached — greet back and ask how you can help. Do NOT call any tool on a pure greeting.

══ ORDER WORKFLOW ══
When a customer asks about "my order" without specifying which one:
  Step 1 → Call think ALONE. Then call get_order_history(email from header).
  Step 2 → 0 orders: "There are no orders on this account."
            1 order: use it directly.
            2+ orders: list them (item name — date — status), ask which one.
  Step 3 → Wait for the customer to pick one.
  Step 4 → Call think ALONE. Then call get_order_details(confirmed_order_id).

IMPORTANT: If get_order_details was already called for an order this session,
do NOT call it again. The data is in your history — use it.

When a customer wants to change the delivery date:
  - Must have a confirmed order_id before calling change_delivery_date.
  - If customer says "sooner" / no specific date: call think ALONE first.
    Then get_order_details if NOT already fetched, read estimated_warehouse_date,
    compute earliest = warehouse_date + 1 day, tell the customer and wait for confirmation.
  - Never ask the customer to supply a date they cannot know.

══ CANNOT DO ══
Cannot: upgrade shipping speed, expedite, waive fees, modify order contents,
promise delivery dates beyond what the data shows.

══ KNOWLEDGE CONTEXT ══
{knowledge_context}

══ TOOL CALLING RULES (STRICT) ══
ALWAYS use the structured tool_calls format. NEVER put function calls in plain text.
NEVER use <function>...</function> format. NEVER describe a tool call in words.
If a tool is needed: call it via tool_calls. Do not write a text response at the same time.
""".strip()


def _build_history_summary(old_messages: list[Message]) -> Message | None:
    """
    Compress old turns into a compact summary message inserted as a system-style
    context block. This is purely rule-based — no LLM call, no latency.

    Extracts:
    - What the customer asked (truncated)
    - What tools were called and key data from results
    - What the agent replied (truncated)
    """
    if not old_messages:
        return None

    turns = []
    current_turn: dict = {}

    for msg in old_messages:
        if msg.role == Role.user:
            if current_turn:
                turns.append(current_turn)
            current_turn = {
                "user":         msg.content[:120].replace("\n", " "),
                "tools_called": [],
                "tool_data":    [],
                "reply":        "",
            }

        elif msg.role == Role.assistant:
            if msg.content and msg.content.startswith("__tool_calls__:"):
                try:
                    payload = json.loads(msg.content[len("__tool_calls__:"):])
                    for tc in payload:
                        # Skip `think` in the summary — it has no useful data
                        if tc["name"] != "think":
                            current_turn.setdefault("tools_called", []).append(tc["name"])
                except Exception:
                    pass
            else:
                current_turn["reply"] = msg.content[:150].replace("\n", " ")

        elif msg.role == Role.tool:
            try:
                result = json.loads(msg.content)
                if result.get("success") and result.get("data"):
                    data = result["data"]
                    snippet = _extract_tool_snippet(msg.name or "", data)
                    if snippet:
                        current_turn.setdefault("tool_data", []).append(snippet)
            except Exception:
                pass

    if current_turn:
        turns.append(current_turn)

    if not turns:
        return None

    lines = ["[Earlier conversation summary]"]
    for i, turn in enumerate(turns, 1):
        parts = [f"Turn {i}: Customer: \"{turn.get('user', '')[:100]}\""]
        if turn.get("tools_called"):
            parts.append(f"Tools: {', '.join(turn['tools_called'])}")
        if turn.get("tool_data"):
            parts.append(f"Data: {' | '.join(turn['tool_data'])}")
        if turn.get("reply"):
            parts.append(f"Agent: \"{turn['reply'][:120]}\"")
        lines.append(" → ".join(parts))

    summary_content = "\n".join(lines)
    logger.info(
        f"[CONTEXT] History compressed: {len(old_messages)} messages → "
        f"~{max(1, len(summary_content) // 4)} tokens summary"
    )

    return Message(role=Role.user, content=summary_content)


def _extract_tool_snippet(tool_name: str, data: dict) -> str:
    """Pull the most useful facts from a tool result for the summary."""
    try:
        if tool_name == "get_order_history":
            orders = data.get("orders", [])
            if orders:
                summaries = []
                for o in orders[:3]:
                    items = ", ".join(o.get("items", [])[:2])
                    summaries.append(f"{o['order_id'][-8:]} ({items}, {o['status']})")
                return f"Orders: {' | '.join(summaries)}"

        elif tool_name == "get_order_details":
            oid    = data.get("_id", "")[-8:]
            status = data.get("status", "")
            est    = data.get("estimated_destination_date", "")[:10]
            items  = ", ".join(p.get("name", "")[:30] for p in data.get("products", [])[:2])
            return f"Order {oid}: {status}, est. {est}, items: {items}"

        elif tool_name == "get_user_profile":
            return (
                f"Customer: {data.get('name', '')} {data.get('surname', '')}, "
                f"tier: {data.get('loyaltyTier', '')}, "
                f"points: {data.get('loyaltyPoints', '')}, "
                f"status: {data.get('accountStatus', '')}"
            )

        elif tool_name == "get_return_status":
            return f"Return status: {data.get('status', '')} for order {str(data.get('orderId', ''))[-8:]}"

        elif tool_name == "change_delivery_date":
            return f"Date change outcome: {data.get('outcome', '')} for {data.get('requested_date', '')}"

        elif tool_name == "change_delivery_address":
            addr = data.get("new_address", {})
            return f"Address change: {data.get('outcome', '')} → {addr.get('city', '')}, {addr.get('country', '')}"

    except Exception:
        pass
    return ""


def _split_history_into_turns(history: list[Message]) -> list[list[Message]]:
    """
    Group messages into turns by user message boundaries.
    Returns a list of turns, each turn is a list of messages.
    """
    turns  = []
    current: list[Message] = []

    for msg in history:
        if msg.role == Role.user and current:
            turns.append(current)
            current = []
        current.append(msg)

    if current:
        turns.append(current)

    return turns


async def run_agent(
    request:      ChatRequest,
    llm:          LLMBase,
    policy_store: FilePolicyStore,
    tools:        list[BaseTool],
    history:      list[Message] | None = None,
) -> AgentResponse:

    knowledge_context = policy_store.build_context(request.message)
    system_prompt     = SYSTEM_PROMPT_TEMPLATE.format(
        knowledge_context=knowledge_context
    )

    # ── History trimming ──────────────────────────────────────────────────────
    messages: list[Message] = []

    if history:
        all_turns     = _split_history_into_turns(history)
        old_turns     = all_turns[:-VERBATIM_TURNS] if len(all_turns) > VERBATIM_TURNS else []
        recent_turns  = all_turns[-VERBATIM_TURNS:]

        old_messages    = [msg for turn in old_turns for msg in turn]
        recent_messages = [msg for turn in recent_turns for msg in turn]

        if old_messages:
            summary_msg = _build_history_summary(old_messages)
            if summary_msg:
                messages.append(summary_msg)

        messages.extend(recent_messages)

        logger.info(
            f"[CONTEXT] History: {len(all_turns)} total turns — "
            f"{len(old_turns)} compressed, {len(recent_turns)} verbatim — "
            f"{len(messages)} messages passed to LLM"
        )
    else:
        logger.info("[CONTEXT] History: first turn — no history")

    # ── Build user message ────────────────────────────────────────────────────

    is_first_turn = not history
    user_content  = request.message

    # ALWAYS inject identity header — not just on first turn.
    # Without this, after history compression the model loses the email
    # and guesses a placeholder like customer@example.com on turn 2+.
    identity_parts = []
    if request.user_email:
        identity_parts.append(f"Customer email: {request.user_email}")
    if request.order_id:
        identity_parts.append(f"Confirmed order ID: {request.order_id}")
    if identity_parts:
        header = "[" + " | ".join(identity_parts) + "]"
        user_content = f"{header}\n{request.message}"

    messages.append(Message(role=Role.user, content=user_content))

    # ── Log total estimated input size (now including schema tokens) ──────────
    #
    # Previous estimate only counted message content — that explained why logs
    # showed ~1,700-2,750 tokens but Groq billed 8,000-11,000.
    # The missing cost was:
    #   - Tool schemas (sent every iteration): ~250 tokens × N tools
    #   - max_tokens reservation: groq_max_tokens counted against TPD billing
    # We still can't know the post-pruning schema count here (that happens inside
    # GroqService), but we log the baseline (unpruned) to make the gap visible.

    history_tokens  = sum(max(1, len(m.content) // 4) for m in messages if m.content)
    prompt_tokens   = max(1, len(system_prompt) // 4)
    n_schemas       = len(tools)
    schema_tokens   = n_schemas * _TOKENS_PER_SCHEMA

    logger.info(
        f"[CONTEXT] Estimated input — "
        f"system prompt: ~{prompt_tokens} tokens | "
        f"messages: ~{history_tokens} tokens | "
        f"schemas (unpruned, ×2 iters): ~{schema_tokens * 2} tokens | "
        f"max_tokens reservation: ~{getattr(__import__('backend.core.config', fromlist=['get_settings']).get_settings(), 'groq_max_tokens', 1024)} tokens | "
        f"rough total estimate: ~{prompt_tokens + history_tokens + schema_tokens * 2} tokens"
    )

    logger.info(
        f"Running agent — session={request.session_id} "
        f"email={request.user_email} first_turn={is_first_turn}"
    )

    response = await llm.chat(
        messages      = messages,
        tools         = tools,
        system_prompt = system_prompt,
    )

    logger.info(
        f"Agent done — session={request.session_id} "
        f"tools_called={[t.tool_name for t in response.tool_calls]}"
    )

    return response