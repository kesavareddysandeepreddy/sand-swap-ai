import { ChatWindow } from "../components/chat/ChatWindow";
import { MessageComposer } from "../components/chat/MessageComposer";
import type { ChatMessage } from "../types/chat";

interface ChatPageProps {
    messages: ChatMessage[];
    isSending: boolean;
    error: string | null;
    onSendMessage: (message: string) => Promise<void>;
}

export const ChatPage = ({
    messages,
    isSending,
    error,
    onSendMessage,
}: ChatPageProps) => {
    return (
        <div className="chat-page">
            {error ? <p className="error-banner">{error}</p> : null}
            <ChatWindow messages={messages} isSending={isSending} />
            <MessageComposer isSending={isSending} onSendMessage={onSendMessage} />
        </div>
    );
};
