// frontend/src/hooks/useChat.js

import { useState, useCallback, useRef } from "react";
import { sendMessage, getNewSession } from "../api";

export function useChat(userEmail, orderId) {
  const [messages,   setMessages]   = useState([]);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const sessionRef = useRef(null);

  const ensureSession = useCallback(async () => {
    if (!sessionRef.current) {
      sessionRef.current = await getNewSession();
    }
    return sessionRef.current;
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;

    const userMsg = { role: "user", content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const sessionId = await ensureSession();
      const response  = await sendMessage({
        message:   text,
        sessionId,
        userEmail,
        orderId,
      });

      const botMsg = {
        role:          "assistant",
        content:       response.reply,
        id:            Date.now() + 1,
        wasEscalated:  response.was_escalated,
        timestamp:     response.timestamp,
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      setError(err.message);
      const errMsg = {
        role:    "assistant",
        content: "Sorry, I couldn't process that. Please try again.",
        id:      Date.now() + 1,
        isError: true,
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  }, [loading, userEmail, orderId, ensureSession]);

  const reset = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionRef.current = null;
  }, []);

  return { messages, loading, error, send, reset };
}