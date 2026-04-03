// frontend/src/components/MessageBubble.jsx

export function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`msg-row ${isUser ? "msg-row--user" : "msg-row--bot"}`}>
      {!isUser && (
        <div className="avatar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"
              fill="currentColor" opacity="0.7"/>
          </svg>
        </div>
      )}
      <div className={`bubble ${isUser ? "bubble--user" : "bubble--bot"} ${message.isError ? "bubble--error" : ""}`}>
        <p className="bubble__text">{message.content}</p>
        {message.wasEscalated && (
          <span className="escalation-badge">Escalated to team</span>
        )}
      </div>
    </div>
  );
}