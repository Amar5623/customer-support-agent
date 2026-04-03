// frontend/src/api.js

const BASE_URL = "/api";

export async function getNewSession() {
  const res = await fetch(`${BASE_URL}/session/new`);
  if (!res.ok) throw new Error("Failed to create session");
  const data = await res.json();
  return data.session_id;
}

export async function sendMessage({ message, sessionId, userEmail, orderId }) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      user_email: userEmail || null,
      order_id:   orderId   || null,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Something went wrong");
  }

  return res.json();
}