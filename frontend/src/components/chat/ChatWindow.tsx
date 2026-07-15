import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "../../types/chat";
import { formatTimestamp } from "../../utils/date";

interface ChatWindowProps {
    messages: ChatMessage[];
    isSending: boolean;
}

export const ChatWindow = ({ messages, isSending }: ChatWindowProps) => {
    const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
    const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

    useEffect(() => {
        bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [messages, isSending]);

    const copyMessage = async (messageId: string, content: string) => {
        try {
            await navigator.clipboard.writeText(content);
            setCopiedMessageId(messageId);
            window.setTimeout(() => {
                setCopiedMessageId((current) => (current === messageId ? null : current));
            }, 1200);
        } catch {
            setCopiedMessageId(null);
        }
    };

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
                        <div className="message-header-actions">
                            {message.role === "assistant" ? (
                                <button
                                    type="button"
                                    className="message-copy-button"
                                    onClick={() => {
                                        void copyMessage(message.id, message.content);
                                    }}
                                >
                                    {copiedMessageId === message.id ? "Copied" : "Copy"}
                                </button>
                            ) : null}
                            <time dateTime={message.createdAt}>{formatTimestamp(message.createdAt)}</time>
                        </div>
                    </header>
                    {message.role === "assistant" ? (
                        <div className="message-markdown">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    a: ({ children, ...props }) => (
                                        <a {...props} target="_blank" rel="noreferrer noopener">
                                            {children}
                                        </a>
                                    ),
                                }}
                            >
                                {message.content}
                            </ReactMarkdown>
                        </div>
                    ) : (
                        <p>{message.content}</p>
                    )}
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
