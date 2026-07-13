import { describe, expect, it } from "vitest";

import {
    clearChatState,
    loadChatState,
    persistChatState,
} from "./chatStorage";

describe("chatStorage owner isolation", () => {
    it("keeps chat state separated by owner id", () => {
        window.localStorage.clear();

        persistChatState(
            "user-a",
            [
                {
                    id: "conv-a",
                    title: "A",
                    messages: [],
                    updatedAt: "2026-01-01T00:00:00.000Z",
                },
            ],
            "conv-a"
        );

        persistChatState(
            "user-b",
            [
                {
                    id: "conv-b",
                    title: "B",
                    messages: [],
                    updatedAt: "2026-01-01T00:00:00.000Z",
                },
            ],
            "conv-b"
        );

        const userA = loadChatState("user-a");
        const userB = loadChatState("user-b");

        expect(userA.conversations).toHaveLength(1);
        expect(userA.conversations[0].id).toBe("conv-a");
        expect(userA.activeConversationId).toBe("conv-a");

        expect(userB.conversations).toHaveLength(1);
        expect(userB.conversations[0].id).toBe("conv-b");
        expect(userB.activeConversationId).toBe("conv-b");
    });

    it("clears only the targeted owner cache", () => {
        window.localStorage.clear();

        persistChatState(
            "anon-1",
            [
                {
                    id: "conv-anon",
                    title: "Anon",
                    messages: [],
                    updatedAt: "2026-01-01T00:00:00.000Z",
                },
            ],
            "conv-anon"
        );

        persistChatState(
            "user-1",
            [
                {
                    id: "conv-user",
                    title: "User",
                    messages: [],
                    updatedAt: "2026-01-01T00:00:00.000Z",
                },
            ],
            "conv-user"
        );

        clearChatState("anon-1");

        expect(loadChatState("anon-1").conversations).toEqual([]);
        expect(loadChatState("user-1").conversations).toHaveLength(1);
        expect(loadChatState("user-1").conversations[0].id).toBe("conv-user");
    });
});
