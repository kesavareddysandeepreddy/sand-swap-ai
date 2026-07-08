import type { ConversationState } from "../../types/chat";
import { formatTimestamp } from "../../utils/date";

interface ConversationSidebarProps {
  conversations: ConversationState[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
}

export const ConversationSidebar = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}: ConversationSidebarProps) => {
  return (
    <aside className="sidebar">
      <button className="new-chat-button" type="button" onClick={onNewConversation}>
        New Conversation
      </button>
      <ul className="conversation-list">
        {conversations.length === 0 ? (
          <li className="conversation-empty">No conversations yet.</li>
        ) : (
          conversations.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                className={`conversation-item ${
                  activeConversationId === conversation.id ? "conversation-item--active" : ""
                }`}
                onClick={() => onSelectConversation(conversation.id)}
              >
                <span className="conversation-title">{conversation.title}</span>
                <span className="conversation-time">
                  {formatTimestamp(conversation.updatedAt)}
                </span>
              </button>
            </li>
          ))
        )}
      </ul>
    </aside>
  );
};
