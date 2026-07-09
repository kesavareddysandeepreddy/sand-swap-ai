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
    onRenameConversation: (id: string, nextTitle: string) => void;
    onDeleteConversation: (id: string) => void;
}

export const AppLayout = ({
    health,
    healthLoading,
    healthError,
    conversations,
    activeConversationId,
    onSelectConversation,
    onNewConversation,
    onRenameConversation,
    onDeleteConversation,
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
                    onRenameConversation={onRenameConversation}
                    onDeleteConversation={onDeleteConversation}
                />
                <main className="main-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};
