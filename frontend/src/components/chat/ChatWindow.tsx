import type { ChatMessage } from "../../types/chat";
import { formatTimestamp } from "../../utils/date";

interface ChatWindowProps {
    messages: ChatMessage[];
    isSending: boolean;
}

export const ChatWindow = ({ messages, isSending }: ChatWindowProps) => {
    if (!messages.length) {
        return (
            <section className="chat-window chat-window--empty">
                <p>Start a conversation to see responses from SandSwap AI.</p>
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
            {isSending ? <p className="sending-indicator">Assistant is thinking...</p> : null}
        </section>
    );
};
