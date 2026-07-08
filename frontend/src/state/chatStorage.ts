import type { ConversationState } from "../types/chat";

const STORAGE_KEY = "sand-swap-chat-state-v1";

interface PersistedChatState {
    conversations: ConversationState[];
    activeConversationId: string | null;
}

const isConversationState = (value: unknown): value is ConversationState => {
    if (typeof value !== "object" || value === null) {
        return false;
    }

    const candidate = value as Partial<ConversationState>;
    return (
        typeof candidate.id === "string"
        && typeof candidate.title === "string"
        && typeof candidate.updatedAt === "string"
        && Array.isArray(candidate.messages)
    );
};

export const loadChatState = (): PersistedChatState => {
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return { conversations: [], activeConversationId: null };
        }

        const parsed = JSON.parse(raw) as Partial<PersistedChatState>;
        const conversations = Array.isArray(parsed.conversations)
            ? parsed.conversations.filter(isConversationState)
            : [];

        return {
            conversations,
            activeConversationId:
                typeof parsed.activeConversationId === "string"
                    ? parsed.activeConversationId
                    : null,
        };
    } catch {
        return { conversations: [], activeConversationId: null };
    }
};

export const persistChatState = (
    conversations: ConversationState[],
    activeConversationId: string | null
): void => {
    const payload: PersistedChatState = {
        conversations,
        activeConversationId,
    };

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
};
