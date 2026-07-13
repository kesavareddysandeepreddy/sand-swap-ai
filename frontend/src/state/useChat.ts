import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { ConversationState } from "../types/chat";
import { createId } from "../utils/ids";
import { loadChatState, persistChatState } from "./chatStorage";

const DRAFT_ID_PREFIX = "draft-";

const getConversationTitle = (message: string): string =>
    message.length > 36 ? `${message.slice(0, 36)}...` : message;

const upsertConversation = (
    conversations: ConversationState[],
    nextConversation: ConversationState
): ConversationState[] => {
    const index = conversations.findIndex(
        (conversation) => conversation.id === nextConversation.id
    );

    if (index === -1) {
        return [nextConversation, ...conversations];
    }

    return conversations.map((conversation) =>
        conversation.id === nextConversation.id ? nextConversation : conversation
    );
};

const dedupeConversations = (
    conversations: ConversationState[]
): ConversationState[] => {
    const seen = new Set<string>();
    return conversations.filter((conversation) => {
        if (seen.has(conversation.id)) {
            return false;
        }
        seen.add(conversation.id);
        return true;
    });
};

const mergeConversationMessages = (
    left: ConversationState,
    right: ConversationState
): ConversationState => {
    const seen = new Set<string>();
    const merged = [...left.messages, ...right.messages].filter((message) => {
        if (seen.has(message.id)) {
            return false;
        }
        seen.add(message.id);
        return true;
    });

    return {
        ...right,
        messages: merged,
    };
};

export const useChat = (ownerId: string, storageScopeId: string) => {
    const [initialState] = useState(() => loadChatState(storageScopeId));

    const [conversations, setConversations] = useState<ConversationState[]>(initialState.conversations);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(initialState.activeConversationId);
    const [isSending, setIsSending] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useLayoutEffect(() => {
        const next = loadChatState(storageScopeId);
        setConversations(next.conversations);
        setActiveConversationId(next.activeConversationId);
        setError(null);
    }, [storageScopeId]);

    useEffect(() => {
        persistChatState(storageScopeId, conversations, activeConversationId);
    }, [storageScopeId, conversations, activeConversationId]);

    const activeConversation = useMemo(
        () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
        [conversations, activeConversationId]
    );

    const sendMessage = async (message: string): Promise<void> => {
        const content = message.trim();
        if (!content) {
            return;
        }

        setIsSending(true);
        setError(null);

        const isNewConversation =
            activeConversationId === null
            || activeConversationId.startsWith(DRAFT_ID_PREFIX);
        const optimisticConversationId = activeConversationId ?? `${DRAFT_ID_PREFIX}${createId()}`;
        const requestConversationId =
            optimisticConversationId.startsWith(DRAFT_ID_PREFIX)
                ? undefined
                : optimisticConversationId;
        const userMessage = {
            id: createId(),
            role: "user" as const,
            content,
            createdAt: new Date().toISOString(),
        };

        setConversations((previous) => {
            const existing = previous.find((conversation) => conversation.id === optimisticConversationId);

            if (existing) {
                const lastMessage = existing.messages[existing.messages.length - 1];
                const hasDuplicateTail =
                    lastMessage?.role === "user"
                    && lastMessage.content === userMessage.content;

                return previous.map((conversation) =>
                    conversation.id === optimisticConversationId
                        ? {
                            ...conversation,
                            messages: hasDuplicateTail
                                ? conversation.messages
                                : [...conversation.messages, userMessage],
                            updatedAt: userMessage.createdAt,
                        }
                        : conversation
                );
            }

            return upsertConversation(previous, {
                id: optimisticConversationId,
                title: getConversationTitle(content),
                messages: [userMessage],
                updatedAt: userMessage.createdAt,
            });
        });

        setActiveConversationId(optimisticConversationId);

        try {
            const response = await apiClient.sendChatMessage({
                user_id: ownerId,
                message: content,
                conversation_id: requestConversationId,
            });

            const assistantMessage = {
                id: createId(),
                role: "assistant" as const,
                content: response.response,
                createdAt: new Date().toISOString(),
            };

            setConversations((previous) => {
                const source = previous.find(
                    (conversation) => conversation.id === optimisticConversationId
                );
                const target = previous.find(
                    (conversation) => conversation.id === response.conversation_id
                );

                if (!source) {
                    return previous;
                }

                const withAssistant: ConversationState = {
                    ...source,
                    id: response.conversation_id,
                    title:
                        source.title === "New conversation"
                            ? getConversationTitle(content)
                            : source.title,
                    messages: [...source.messages, assistantMessage],
                    updatedAt: assistantMessage.createdAt,
                };

                const merged = target
                    ? mergeConversationMessages(withAssistant, {
                        ...target,
                        updatedAt: withAssistant.updatedAt,
                    })
                    : withAssistant;

                const filtered = previous.filter(
                    (conversation) =>
                        conversation.id !== optimisticConversationId
                        && conversation.id !== response.conversation_id
                );

                return dedupeConversations([merged, ...filtered]);
            });

            setActiveConversationId(response.conversation_id);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to send message.");

            if (isNewConversation) {
                setConversations((previous) =>
                    previous.filter((conversation) => conversation.id !== optimisticConversationId)
                );
                setActiveConversationId(null);
            }
        } finally {
            setIsSending(false);
        }
    };

    const startNewConversation = () => {
        if (activeConversation?.id.startsWith(DRAFT_ID_PREFIX)
            && activeConversation.messages.length === 0) {
            setError(null);
            return;
        }

        const existingEmptyDraft = conversations.find(
            (conversation) =>
                conversation.id.startsWith(DRAFT_ID_PREFIX)
                && conversation.messages.length === 0
        );

        if (existingEmptyDraft) {
            setActiveConversationId(existingEmptyDraft.id);
            setError(null);
            return;
        }

        const now = new Date().toISOString();
        const draftConversation: ConversationState = {
            id: `${DRAFT_ID_PREFIX}${createId()}`,
            title: "New conversation",
            messages: [],
            updatedAt: now,
        };

        setConversations((previous) => upsertConversation(previous, draftConversation));
        setActiveConversationId(draftConversation.id);
        setError(null);
    };

    const renameConversation = (conversationId: string, nextTitle: string) => {
        const trimmedTitle = nextTitle.trim();
        if (!trimmedTitle) {
            return;
        }

        setConversations((previous) =>
            previous.map((conversation) =>
                conversation.id === conversationId
                    ? {
                        ...conversation,
                        title: trimmedTitle,
                    }
                    : conversation
            )
        );
    };

    const deleteConversation = (conversationId: string) => {
        setConversations((previous) => {
            const next = previous.filter(
                (conversation) => conversation.id !== conversationId
            );

            setActiveConversationId((previousActive) => {
                if (previousActive !== conversationId) {
                    return previousActive;
                }
                return next[0]?.id ?? null;
            });

            return next;
        });

        setError(null);
    };

    return {
        userId: ownerId,
        storageScopeId,
        conversations,
        activeConversation,
        activeConversationId,
        setActiveConversationId,
        isSending,
        error,
        sendMessage,
        startNewConversation,
        renameConversation,
        deleteConversation,
    };
};
