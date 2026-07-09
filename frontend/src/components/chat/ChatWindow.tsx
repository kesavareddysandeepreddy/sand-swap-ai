import { useEffect, useRef } from "react";

import type { ChatMessage } from "../../types/chat";
import { formatTimestamp } from "../../utils/date";

interface ChatWindowProps {
    messages: ChatMessage[];
    isSending: boolean;
}

export const ChatWindow = ({ messages, isSending }: ChatWindowProps) => {
    const bottomAnchorRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [messages, isSending]);

    if (!messages.length) {
        return (
            <section className="chat-window chat-window--empty">
                <div className="empty-state">
                    <h2>Welcome to SandSwap AI</h2>
                    <p>Ask anything to begin your conversation.</p>
                </div>
            </section>
        );
    }

    return (
        <section className="chat-window" aria-live="polite">
            {messages.map((message) => (
                <article
                    key={message.id}
                    className={`message message--${message.role}`}
                >
                    <header className="message-header">
                        <span>{message.role === "user" ? "You" : "Assistant"}</span>
                        <time dateTime={message.createdAt}>{formatTimestamp(message.createdAt)}</time>
                    </header>
                    <p>{message.content}</p>
                </article>
            ))}
            {isSending ? (
                <p className="sending-indicator">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    Assistant is typing...
                </p>
            ) : null}
            <div ref={bottomAnchorRef} aria-hidden="true" />
        </section>
    );
};
