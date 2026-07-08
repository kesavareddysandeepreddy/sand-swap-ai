import { useMemo, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type { ConversationState } from "../types/chat";
import { createId } from "../utils/ids";

const DEFAULT_USER_ID = "local-user";

const getConversationTitle = (message: string): string =>
    message.length > 36 ? `${message.slice(0, 36)}...` : message;

export const useChat = () => {
    const [userId, setUserId] = useState<string>(DEFAULT_USER_ID);
    const [conversations, setConversations] = useState<ConversationState[]>([]);
    const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
    const [isSending, setIsSending] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

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

        const optimisticConversationId = activeConversationId ?? createId();
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
                conversation_id: activeConversationId ?? undefined,
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
                        messages: [...conversation.messages, assistantMessage],
                        updatedAt: assistantMessage.createdAt,
                    };
                })
            );

            setActiveConversationId(response.conversation_id);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to send message.");
        } finally {
            setIsSending(false);
        }
    };

    const startNewConversation = () => {
        setActiveConversationId(null);
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
