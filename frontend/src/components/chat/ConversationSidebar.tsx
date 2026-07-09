import { useState } from "react";
import { NavLink } from "react-router-dom";

import type { ConversationState } from "../../types/chat";
import { formatTimestamp } from "../../utils/date";

interface ConversationSidebarProps {
    conversations: ConversationState[];
    activeConversationId: string | null;
    onSelectConversation: (id: string) => void;
    onNewConversation: () => void;
    onRenameConversation: (id: string, nextTitle: string) => void;
    onDeleteConversation: (id: string) => void;
}

export const ConversationSidebar = ({
    conversations,
    activeConversationId,
    onSelectConversation,
    onNewConversation,
    onRenameConversation,
    onDeleteConversation,
}: ConversationSidebarProps) => {
    const [openMenuId, setOpenMenuId] = useState<string | null>(null);

    const handleRename = (conversation: ConversationState) => {
        const renamed = window.prompt("Rename conversation", conversation.title);
        if (!renamed) {
            setOpenMenuId(null);
            return;
        }
        onRenameConversation(conversation.id, renamed);
        setOpenMenuId(null);
    };

    const handleDelete = (conversation: ConversationState) => {
        const shouldDelete = window.confirm(
            `Delete conversation "${conversation.title}"?`
        );
        if (!shouldDelete) {
            return;
        }
        onDeleteConversation(conversation.id);
        setOpenMenuId(null);
    };

    return (
        <aside className="sidebar">
            <nav className="sidebar-nav" aria-label="Primary">
                <NavLink
                    to="/chat"
                    className={({ isActive }) =>
                        `sidebar-nav-link ${isActive ? "sidebar-nav-link--active" : ""}`
                    }
                >
                    Chat
                </NavLink>
                <NavLink
                    to="/memory"
                    className={({ isActive }) =>
                        `sidebar-nav-link ${isActive ? "sidebar-nav-link--active" : ""}`
                    }
                >
                    Memory
                </NavLink>
            </nav>
            <button className="new-chat-button" type="button" onClick={onNewConversation}>
                New Conversation
            </button>
            <ul className="conversation-list">
                {conversations.length === 0 ? (
                    <li className="conversation-empty">No conversations yet.</li>
                ) : (
                    conversations.map((conversation) => (
                        <li key={conversation.id}>
                            <div
                                className={`conversation-item ${activeConversationId === conversation.id ? "conversation-item--active" : ""
                                    }`}
                            >
                                <button
                                    type="button"
                                    className="conversation-select"
                                    onClick={() => onSelectConversation(conversation.id)}
                                >
                                    <span className="conversation-title">{conversation.title}</span>
                                    <span className="conversation-time">
                                        {formatTimestamp(conversation.updatedAt)}
                                    </span>
                                </button>

                                <div className="conversation-actions">
                                    <button
                                        type="button"
                                        className="conversation-menu-trigger"
                                        aria-label="Conversation options"
                                        onClick={() =>
                                            setOpenMenuId((previous) =>
                                                previous === conversation.id ? null : conversation.id
                                            )
                                        }
                                    >
                                        ⋯
                                    </button>
                                    {openMenuId === conversation.id ? (
                                        <div className="conversation-menu" role="menu">
                                            <button
                                                type="button"
                                                onClick={() => handleRename(conversation)}
                                            >
                                                Rename
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => handleDelete(conversation)}
                                            >
                                                Delete
                                            </button>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </li>
                    ))
                )}
            </ul>
        </aside>
    );
};
