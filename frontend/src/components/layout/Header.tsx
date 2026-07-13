import type { HealthResponse, WorkspaceRecord } from "../../types/api";
import { HealthIndicator } from "../status/HealthIndicator";

interface HeaderProps {
    health: HealthResponse | null;
    healthLoading: boolean;
    healthError: string | null;
    isAuthenticated: boolean;
    displayName: string | null;
    email: string | null;
    avatarUrl?: string | null;
    workspaceScopeId: string;
    workspaces: WorkspaceRecord[];
    activeWorkspaceId: string | null;
    isWorkspaceLoading: boolean;
    onSwitchWorkspace: (workspaceId: string) => Promise<unknown>;
    onCreateWorkspace: (name: string, description?: string) => Promise<unknown>;
    onRenameWorkspace: (workspaceId: string, name: string) => Promise<unknown>;
    onDeleteWorkspace: (workspaceId: string) => Promise<void>;
    onGoogleSignIn: () => Promise<boolean>;
    onLogout: () => void;
}

export const Header = ({
    health,
    healthLoading,
    healthError,
    isAuthenticated,
    displayName,
    email,
    avatarUrl,
    workspaceScopeId,
    workspaces,
    activeWorkspaceId,
    isWorkspaceLoading,
    onSwitchWorkspace,
    onCreateWorkspace,
    onRenameWorkspace,
    onDeleteWorkspace,
    onGoogleSignIn,
    onLogout,
}: HeaderProps) => {
    const activeWorkspaceName =
        workspaces.find((workspace) => workspace.id === activeWorkspaceId)?.name
        ?? "Workspace";

    return (
        <header className="app-header">
            <div>
                <p className="eyebrow">SandSwap AI</p>
                <h1 className="title">Local Chat Console</h1>
            </div>
            <div className="header-meta">
                <HealthIndicator health={health} isLoading={healthLoading} error={healthError} />
                {isAuthenticated ? (
                    <details className="profile-dropdown">
                        <summary className="profile-trigger">
                            {avatarUrl ? (
                                <img className="profile-avatar" src={avatarUrl} alt="User avatar" />
                            ) : (
                                <span className="profile-avatar-fallback">
                                    {(displayName ?? "U").slice(0, 1).toUpperCase()}
                                </span>
                            )}
                            <span>{displayName ?? "Authenticated User"}</span>
                        </summary>
                        <div className="profile-menu">
                            <p className="profile-name">{displayName ?? "Authenticated User"}</p>
                            <p className="profile-email">{email ?? ""}</p>
                            <p className="profile-workspace-label">Workspace</p>
                            <div className="workspace-switcher-row">
                                <select
                                    className="workspace-select"
                                    value={activeWorkspaceId ?? ""}
                                    disabled={isWorkspaceLoading || workspaces.length === 0}
                                    onChange={(event) => {
                                        void onSwitchWorkspace(event.target.value);
                                    }}
                                >
                                    {workspaces.map((workspace) => (
                                        <option key={workspace.id} value={workspace.id}>
                                            {workspace.name}
                                        </option>
                                    ))}
                                </select>
                                <span className="workspace-active-chip" title={workspaceScopeId}>
                                    {activeWorkspaceName}
                                </span>
                            </div>
                            <div className="workspace-actions-row">
                                <button
                                    type="button"
                                    className="memory-button profile-menu-link"
                                    onClick={() => {
                                        const name = window.prompt("New workspace name");
                                        if (!name || !name.trim()) {
                                            return;
                                        }
                                        void onCreateWorkspace(name.trim());
                                    }}
                                >
                                    New Workspace
                                </button>
                                <button
                                    type="button"
                                    className="memory-button profile-menu-link"
                                    disabled={!activeWorkspaceId}
                                    onClick={() => {
                                        if (!activeWorkspaceId) {
                                            return;
                                        }
                                        const name = window.prompt("Rename workspace", activeWorkspaceName);
                                        if (!name || !name.trim()) {
                                            return;
                                        }
                                        void onRenameWorkspace(activeWorkspaceId, name.trim());
                                    }}
                                >
                                    Rename
                                </button>
                                <button
                                    type="button"
                                    className="memory-button profile-menu-link"
                                    disabled={!activeWorkspaceId || workspaces.length <= 1}
                                    onClick={() => {
                                        if (!activeWorkspaceId) {
                                            return;
                                        }
                                        const confirmed = window.confirm(
                                            `Delete workspace \"${activeWorkspaceName}\"?`
                                        );
                                        if (!confirmed) {
                                            return;
                                        }
                                        void onDeleteWorkspace(activeWorkspaceId);
                                    }}
                                >
                                    Delete
                                </button>
                            </div>
                            <button type="button" className="memory-button profile-menu-link" disabled>
                                Settings
                            </button>
                            <button type="button" className="memory-button" onClick={onLogout}>
                                Sign out
                            </button>
                        </div>
                    </details>
                ) : (
                    <button
                        type="button"
                        className="google-signin-button"
                        onClick={() => {
                            void onGoogleSignIn();
                        }}
                    >
                        Sign in with Google
                    </button>
                )}
            </div>
        </header>
    );
};
