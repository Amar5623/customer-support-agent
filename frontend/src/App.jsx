// frontend/src/App.jsx

import { useState } from "react";
import { ChatWindow } from "./components/ChatWindow";
import "./app.css";

function PreChatForm({ onStart }) {
  const [email,   setEmail]   = useState("");
  const [orderId, setOrderId] = useState("");
  const [error,   setError]   = useState("");

  const handleSubmit = () => {
    if (!email.trim()) {
      setError("Email is required to continue.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }
    onStart(email.trim(), orderId.trim() || null);
  };

  const handleKey = (e) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <div className="prechat">
      <div className="prechat__card">
        <div className="prechat__logo">
          <span className="logo-leaf">🌿</span>
          <span className="logo-text">Leafy</span>
        </div>
        <h1 className="prechat__title">How can we help?</h1>
        <p className="prechat__sub">
          Enter your details and we'll pull up your account instantly.
        </p>

        <div className="form-group">
          <label className="form-label">Email address *</label>
          <input
            className="form-input"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setError(""); }}
            onKeyDown={handleKey}
            autoFocus
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            Order ID
            <span className="form-optional">optional</span>
          </label>
          <input
            className="form-input"
            type="text"
            placeholder="682b73a0..."
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            onKeyDown={handleKey}
          />
          <p className="form-hint">Have a specific order question? Paste your order ID above.</p>
        </div>

        {error && <p className="form-error">{error}</p>}

        <button className="start-btn" onClick={handleSubmit}>
          Start chatting
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>

        <p className="prechat__footer">
          Typically replies in seconds · Available 24/7
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(null); // { email, orderId }

  const handleStart = (email, orderId) => {
    setSession({ email, orderId });
  };

  const handleReset = () => {
    setSession(null);
  };

  return (
    <div className="app">
      {session ? (
        <ChatWindow
          userEmail={session.email}
          orderId={session.orderId}
          onReset={handleReset}
        />
      ) : (
        <PreChatForm onStart={handleStart} />
      )}
    </div>
  );
}