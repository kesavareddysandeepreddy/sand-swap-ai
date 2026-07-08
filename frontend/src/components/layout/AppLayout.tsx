import { Outlet } from "react-router-dom";

import type { HealthResponse } from "../../types/api";
import type { ConversationState } from "../../types/chat";
import { ConversationSidebar } from "../chat/ConversationSidebar";
import { Header } from "./Header";

interface AppLayoutProps {
    health: HealthResponse | null;
    healthLoading: boolean;
    healthError: string | null;
    conversations: ConversationState[];
    activeConversationId: string | null;
    onSelectConversation: (id: string) => void;
    onNewConversation: () => void;
}

export const AppLayout = ({
    health,
    healthLoading,
    healthError,
    conversations,
    activeConversationId,
    onSelectConversation,
    onNewConversation,
}: AppLayoutProps) => {
    return (
        <div className="app-shell">
            <Header health={health} healthLoading={healthLoading} healthError={healthError} />
            <div className="content-grid">
                <ConversationSidebar
                    conversations={conversations}
                    activeConversationId={activeConversationId}
                    onSelectConversation={onSelectConversation}
                    onNewConversation={onNewConversation}
                />
                <main className="main-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};
