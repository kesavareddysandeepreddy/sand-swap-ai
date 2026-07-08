import { useEffect, useMemo, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { ConversationState } from "../types/chat";
import { createId } from "../utils/ids";
import { loadChatState, persistChatState } from "./chatStorage";

const DEFAULT_USER_ID = "local-user";
const DRAFT_ID_PREFIX = "draft-";

const getConversationTitle = (message: string): string =>
    message.length > 36 ? `${message.slice(0, 36)}...` : message;

export const useChat = () => {
    const [initialState] = useState(() => loadChatState());

    const [userId, setUserId] = useState<string>(DEFAULT_USER_ID);
    const [conversations, setConversations] = useState<ConversationState[]>(initialState.conversations);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(initialState.activeConversationId);
    const [isSending, setIsSending] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        persistChatState(conversations, activeConversationId);
    }, [conversations, activeConversationId]);

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

        const isNewConversation = activeConversationId === null;
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
                return previous.map((conversation) =>
                    conversation.id === optimisticConversationId
                        ? {
                            ...conversation,
                            messages: [...conversation.messages, userMessage],
                            updatedAt: userMessage.createdAt,
                        }
                        : conversation
                );
            }

            return [
                {
                    id: optimisticConversationId,
                    title: getConversationTitle(content),
                    messages: [userMessage],
                    updatedAt: userMessage.createdAt,
                },
                ...previous,
            ];
        });

        setActiveConversationId(optimisticConversationId);

        try {
            const response = await apiClient.sendChatMessage({
                user_id: userId,
                message: content,
                conversation_id: requestConversationId,
            });

            const assistantMessage = {
                id: createId(),
                role: "assistant" as const,
                content: response.response,
                createdAt: new Date().toISOString(),
            };

            setConversations((previous) =>
                previous.map((conversation) => {
                    if (conversation.id !== optimisticConversationId) {
                        return conversation;
                    }

                    return {
                        ...conversation,
                        id: response.conversation_id,
                        title:
                            conversation.title === "New conversation"
                                ? getConversationTitle(content)
                                : conversation.title,
                        messages: [...conversation.messages, assistantMessage],
                        updatedAt: assistantMessage.createdAt,
                    };
                })
            );

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
        const now = new Date().toISOString();
        const draftConversation: ConversationState = {
            id: `${DRAFT_ID_PREFIX}${createId()}`,
            title: "New conversation",
            messages: [],
            updatedAt: now,
        };

        setConversations((previous) => [draftConversation, ...previous]);
        setActiveConversationId(draftConversation.id);
        setError(null);
    };

    return {
        userId,
        setUserId,
        conversations,
        activeConversation,
        activeConversationId,
        setActiveConversationId,
        isSending,
        error,
        sendMessage,
        startNewConversation,
    };
};
