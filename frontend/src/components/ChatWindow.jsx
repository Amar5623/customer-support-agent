// frontend/src/components/ChatWindow.jsx

import { useState, useRef, useEffect } from "react";
import { MessageBubble }   from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { useChat }         from "../hooks/useChat";

export function ChatWindow({ userEmail, orderId, onReset }) {
  const { messages, loading, send } = useChat(userEmail, orderId);
  const [input,   setInput]   = useState("");
  const bottomRef             = useRef(null);
  const inputRef              = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    send(text);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = [
    "Where is my order?",
    "What is your return policy?",
    "I want to change my delivery date",
    "How do I track my package?",
  ];

  return (
    <div className="chat-window">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header__info">
          <div className="chat-header__avatar">
            <span>L</span>
            <div className="online-dot" />
          </div>
          <div>
            <p className="chat-header__name">Leafy Support</p>
            <p className="chat-header__status">Online · Usually replies instantly</p>
          </div>
        </div>
        <button className="icon-btn" onClick={onReset} title="Start new chat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
            <path d="M3 3v5h5"/>
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty__icon">🌿</div>
            <p className="chat-empty__title">Hi{userEmail ? `, ${userEmail.split("@")[0]}` : ""}!</p>
            <p className="chat-empty__sub">How can I help you today?</p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} className="suggestion-chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Context bar — show if email or order provided */}
      {(userEmail || orderId) && (
        <div className="context-bar">
          {userEmail && <span className="context-tag">📧 {userEmail}</span>}
          {orderId   && <span className="context-tag">📦 {orderId.slice(-8)}</span>}
        </div>
      )}

      {/* Input */}
      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Type your message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          disabled={loading}
        />
        <button
          className={`send-btn ${input.trim() && !loading ? "send-btn--active" : ""}`}
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="m22 2-7 20-4-9-9-4 20-7z"/>
            <path d="M22 2 11 13"/>
          </svg>
        </button>
      </div>
    </div>
  );
}