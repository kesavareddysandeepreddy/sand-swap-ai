import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ConversationSidebar } from "./ConversationSidebar";

describe("ConversationSidebar", () => {
    it("renders knowledge sources navigation entry", () => {
        render(
            <BrowserRouter>
                <ConversationSidebar
                    conversations={[]}
                    activeConversationId={null}
                    onSelectConversation={vi.fn()}
                    onNewConversation={vi.fn()}
                    onRenameConversation={vi.fn()}
                    onDeleteConversation={vi.fn()}
                />
            </BrowserRouter>
        );

        expect(screen.getByRole("link", { name: "Knowledge Sources" })).toBeInTheDocument();
    });
});
