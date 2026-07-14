import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { useChat } from "./useChat";

vi.mock("../api/client", () => ({
    apiClient: {
        listChatModels: vi.fn(async () => ({ models: ["llama3.2:3b"] })),
        listChatConversations: vi.fn(async () => ({ items: [] })),
        sendChatMessage: vi.fn(),
    },
    ApiError: class ApiError extends Error {
        status: number;
        constructor(message: string, status: number) {
            super(message);
            this.status = status;
        }
    },
}));

describe("useChat conversation restoration", () => {
    beforeEach(() => {
        window.localStorage.clear();
        vi.resetAllMocks();
        vi.mocked(apiClient.listChatModels).mockResolvedValue({ models: ["llama3.2:3b"] });
    });

    it("automatically restores persisted conversations for authenticated project scope", async () => {
        vi.mocked(apiClient.listChatConversations).mockResolvedValue({
            items: [
                {
                    id: "user-1:conv-1",
                    title: "My name is Sandeep.",
                    updated_at: "2026-01-01T00:00:00.000Z",
                    messages: [
                        {
                            id: "m-1",
                            role: "user",
                            content: "My name is Sandeep.",
                            created_at: "2026-01-01T00:00:00.000Z",
                        },
                        {
                            id: "m-2",
                            role: "assistant",
                            content: "Got it.",
                            created_at: "2026-01-01T00:00:01.000Z",
                        },
                    ],
                },
            ],
        });

        const { result } = renderHook(() => useChat("user-1", "user-1:workspace-1:project-1"));

        await waitFor(() => {
            expect(apiClient.listChatConversations).toHaveBeenCalledTimes(1);
            expect(result.current.conversations).toHaveLength(1);
        });

        expect(result.current.activeConversationId).toBe("user-1:conv-1");
        expect(result.current.activeConversation?.messages).toHaveLength(2);
        expect(result.current.activeConversation?.messages[0].createdAt).toBe(
            "2026-01-01T00:00:00.000Z"
        );
    });

    it("does not call server restore for anonymous sessions", async () => {
        const { result } = renderHook(() => useChat("anon-abc", "anon-abc:default:default"));

        await act(async () => {
            await Promise.resolve();
        });

        expect(apiClient.listChatConversations).not.toHaveBeenCalled();
        expect(result.current.conversations).toEqual([]);
    });
});
