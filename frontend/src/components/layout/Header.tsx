import { useEffect, useRef, useState } from "react";

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
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const profileDropdownRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        const onDocumentPointerDown = (event: MouseEvent) => {
            if (!isProfileOpen) {
                return;
            }
            const target = event.target;
            if (!(target instanceof Node)) {
                return;
            }
            if (!profileDropdownRef.current?.contains(target)) {
                setIsProfileOpen(false);
            }
        };

        const onDocumentKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setIsProfileOpen(false);
            }
        };

        document.addEventListener("mousedown", onDocumentPointerDown);
        document.addEventListener("keydown", onDocumentKeyDown);
        return () => {
            document.removeEventListener("mousedown", onDocumentPointerDown);
            document.removeEventListener("keydown", onDocumentKeyDown);
        };
    }, [isProfileOpen]);

    return (
        <header className="app-header">
            <div>
                <p className="eyebrow">SandSwap AI</p>
                <h1 className="title">AI Operating System</h1>
            </div>
            <div className="header-meta">
                <HealthIndicator health={health} isLoading={healthLoading} error={healthError} />
                {isAuthenticated ? (
                    <div className="profile-dropdown" ref={profileDropdownRef}>
                        <button
                            type="button"
                            className="profile-trigger"
                            aria-expanded={isProfileOpen}
                            aria-haspopup="menu"
                            onClick={() => {
                                setIsProfileOpen((previous) => !previous);
                            }}
                        >
                            {avatarUrl ? (
                                <img className="profile-avatar" src={avatarUrl} alt="User avatar" />
                            ) : (
                                <span className="profile-avatar-fallback">
                                    {(displayName ?? "U").slice(0, 1).toUpperCase()}
                                </span>
                            )}
                            <span>{displayName ?? "Authenticated User"}</span>
                        </button>
                        {isProfileOpen ? (
                            <div className="profile-menu" role="menu">
                                <p className="profile-name">{displayName ?? "Authenticated User"}</p>
                                <p className="profile-email">{email ?? ""}</p>
                                <button
                                    type="button"
                                    className="memory-button"
                                    onClick={() => {
                                        setIsProfileOpen(false);
                                        onLogout();
                                    }}
                                >
                                    Sign out
                                </button>
                            </div>
                        ) : null}
                    </div>
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
