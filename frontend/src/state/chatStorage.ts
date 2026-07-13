import type { ConversationState } from "../types/chat";

const STORAGE_KEY_PREFIX = "sand-swap-chat-state-v1";

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

const dedupeConversations = (
    conversations: ConversationState[]
): ConversationState[] => {
    const seen = new Set<string>();
    const unique: ConversationState[] = [];

    for (const conversation of conversations) {
        if (seen.has(conversation.id)) {
            continue;
        }
        seen.add(conversation.id);
        unique.push(conversation);
    }

    return unique;
};

export const loadChatState = (ownerId: string): PersistedChatState => {
    try {
        const storageKey = `${STORAGE_KEY_PREFIX}:${ownerId}`;
        const raw = window.localStorage.getItem(storageKey);
        if (!raw) {
            return { conversations: [], activeConversationId: null };
        }

        const parsed = JSON.parse(raw) as Partial<PersistedChatState>;
        const conversations = Array.isArray(parsed.conversations)
            ? dedupeConversations(parsed.conversations.filter(isConversationState))
            : [];

        const activeConversationId =
            typeof parsed.activeConversationId === "string"
                ? parsed.activeConversationId
                : null;

        const hasActiveConversation = activeConversationId
            ? conversations.some((conversation) => conversation.id === activeConversationId)
            : false;

        return {
            conversations,
            activeConversationId: hasActiveConversation ? activeConversationId : null,
        };
    } catch {
        return { conversations: [], activeConversationId: null };
    }
};

export const persistChatState = (
    ownerId: string,
    conversations: ConversationState[],
    activeConversationId: string | null
): void => {
    const uniqueConversations = dedupeConversations(conversations);
    const hasActiveConversation = activeConversationId
        ? uniqueConversations.some((conversation) => conversation.id === activeConversationId)
        : false;

    const payload: PersistedChatState = {
        conversations: uniqueConversations,
        activeConversationId: hasActiveConversation ? activeConversationId : null,
    };

    const storageKey = `${STORAGE_KEY_PREFIX}:${ownerId}`;
    window.localStorage.setItem(storageKey, JSON.stringify(payload));
};

export const clearChatState = (ownerId: string): void => {
    const storageKey = `${STORAGE_KEY_PREFIX}:${ownerId}`;
    window.localStorage.removeItem(storageKey);
};
