import { Outlet } from "react-router-dom";

import type { HealthResponse } from "../../types/api";
import type { ReturnTypeUseAuth } from "../../types/auth";
import type { ConversationState } from "../../types/chat";
import { ConversationSidebar } from "../chat/ConversationSidebar";
import { Header } from "./Header";

interface AppLayoutProps {
    auth: ReturnTypeUseAuth;
    health: HealthResponse | null;
    healthLoading: boolean;
    healthError: string | null;
    workspaceScopeId: string;
    conversations: ConversationState[];
    activeConversationId: string | null;
    onSelectConversation: (id: string) => void;
    onNewConversation: () => void;
    onRenameConversation: (id: string, nextTitle: string) => void;
    onDeleteConversation: (id: string) => void;
}

export const AppLayout = ({
    auth,
    health,
    healthLoading,
    healthError,
    workspaceScopeId,
    conversations,
    activeConversationId,
    onSelectConversation,
    onNewConversation,
    onRenameConversation,
    onDeleteConversation,
}: AppLayoutProps) => {
    return (
        <div className="app-shell">
            <Header
                health={health}
                healthLoading={healthLoading}
                healthError={healthError}
                isAuthenticated={auth.isAuthenticated}
                displayName={auth.profile?.display_name ?? null}
                email={auth.profile?.email ?? null}
                avatarUrl={auth.profile?.avatar_url ?? null}
                workspaceScopeId={workspaceScopeId}
                workspaces={auth.workspaces}
                projects={auth.projects}
                activeWorkspaceId={auth.activeWorkspaceId}
                activeProjectId={auth.activeProjectId}
                isWorkspaceLoading={auth.isWorkspaceLoading}
                isProjectLoading={auth.isProjectLoading}
                onSwitchWorkspace={auth.switchWorkspace}
                onCreateWorkspace={auth.createWorkspace}
                onRenameWorkspace={auth.renameWorkspace}
                onDeleteWorkspace={auth.deleteWorkspace}
                onSwitchProject={auth.switchProject}
                onCreateProject={auth.createProject}
                onRenameProject={auth.renameProject}
                onDeleteProject={auth.deleteProject}
                onGoogleSignIn={auth.signInWithGooglePopup}
                onLogout={() => void auth.logout()}
            />
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
