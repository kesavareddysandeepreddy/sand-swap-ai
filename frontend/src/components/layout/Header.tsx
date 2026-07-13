import type { HealthResponse } from "../../types/api";
import { HealthIndicator } from "../status/HealthIndicator";

interface HeaderProps {
    health: HealthResponse | null;
    healthLoading: boolean;
    healthError: string | null;
    isAuthenticated: boolean;
    displayName: string | null;
    email: string | null;
    avatarUrl?: string | null;
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
    onGoogleSignIn,
    onLogout,
}: HeaderProps) => {
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
                            <button type="button" className="memory-button profile-menu-link" disabled>
                                Profile
                            </button>
                            <button type="button" className="memory-button profile-menu-link" disabled>
                                Workspace
                            </button>
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
