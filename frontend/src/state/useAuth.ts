import { useCallback, useEffect, useMemo, useState } from "react";

import { apiClient, ApiError } from "../api/client";
import type {
    AuthTokenPair,
    AuthUserProfile,
    WorkspaceRecord,
} from "../types/api";
import { loadAuthSession, persistAuthSession } from "./authStorage";
import { getAnonymousSessionId, rotateAnonymousSessionId } from "./ownerContext";

const WORKSPACE_STORAGE_KEY = "sand-swap-active-workspace-v1";

export const useAuth = () => {
    const [anonymousSessionId, setAnonymousSessionId] = useState<string>(() =>
        getAnonymousSessionId()
    );
    const [session, setSession] = useState<AuthTokenPair | null>(() => {
        const stored = loadAuthSession();
        if (!stored) {
            return null;
        }
        return {
            access_token: stored.accessToken,
            refresh_token: stored.refreshToken,
            token_type: stored.tokenType,
        };
    });
    const [profile, setProfile] = useState<AuthUserProfile | null>(null);
    const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
    const [isWorkspaceLoading, setIsWorkspaceLoading] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const clearSession = useCallback(() => {
        setSession(null);
        setProfile(null);
        setWorkspaces([]);
        persistAuthSession(null);
        apiClient.setAuthToken(null);
        apiClient.setWorkspaceId(null);
        window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
        setAnonymousSessionId(rotateAnonymousSessionId());
    }, []);

    const applySession = useCallback((tokens: AuthTokenPair) => {
        setSession(tokens);
        persistAuthSession({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
            tokenType: tokens.token_type,
        });
        apiClient.setAuthToken(tokens.access_token);
    }, []);

    const refreshSession = useCallback(async (): Promise<boolean> => {
        const current = loadAuthSession();
        if (!current) {
            clearSession();
            return false;
        }
        try {
            const next = await apiClient.refreshToken({
                refresh_token: current.refreshToken,
            });
            applySession(next);
            return true;
        } catch {
            clearSession();
            return false;
        }
    }, [applySession, clearSession]);

    const loadProfile = useCallback(async () => {
        setError(null);
        try {
            const me = await apiClient.getCurrentUser();
            apiClient.setWorkspaceId(me.project_id ?? null);
            if (me.project_id) {
                window.localStorage.setItem(WORKSPACE_STORAGE_KEY, me.project_id);
            } else {
                window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
            }
            setProfile(me);
            return me;
        } catch (err) {
            if (err instanceof ApiError && err.status === 401) {
                const refreshed = await refreshSession();
                if (refreshed) {
                    const me = await apiClient.getCurrentUser();
                    apiClient.setWorkspaceId(me.project_id ?? null);
                    if (me.project_id) {
                        window.localStorage.setItem(WORKSPACE_STORAGE_KEY, me.project_id);
                    } else {
                        window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
                    }
                    setProfile(me);
                    return me;
                }
                setProfile(null);
                return null;
            }
            const message =
                err instanceof ApiError ? err.message : "Failed to load profile.";
            setError(message);
            return null;
        }
    }, [refreshSession]);

    const loadWorkspaces = useCallback(async () => {
        if (!session?.access_token) {
            setWorkspaces([]);
            return [];
        }

        setIsWorkspaceLoading(true);
        try {
            const items = await apiClient.listWorkspaces();
            setWorkspaces(items);
            const active = items.find((workspace) => workspace.is_active) ?? null;
            if (active) {
                apiClient.setWorkspaceId(active.id);
                window.localStorage.setItem(WORKSPACE_STORAGE_KEY, active.id);
                setProfile((previous) =>
                    previous
                        ? {
                            ...previous,
                            project_id: active.id,
                        }
                        : previous
                );
            }
            return items;
        } finally {
            setIsWorkspaceLoading(false);
        }
    }, [session?.access_token]);

    const loginWithPassword = useCallback(
        async (email: string, password: string) => {
            setError(null);
            try {
                const tokens = await apiClient.login({ email, password });
                applySession(tokens);
                await loadProfile();
                await loadWorkspaces();
                return true;
            } catch (err) {
                const message =
                    err instanceof ApiError ? err.message : "Login failed.";
                setError(message);
                return false;
            }
        },
        [applySession, loadProfile, loadWorkspaces]
    );

    const loginWithGoogleCode = useCallback(
        async (code: string, redirectUri: string) => {
            setError(null);
            try {
                const tokens = await apiClient.exchangeGoogleCode({
                    code,
                    redirect_uri: redirectUri,
                });
                applySession(tokens);
                await loadProfile();
                await loadWorkspaces();
                return true;
            } catch (err) {
                const message =
                    err instanceof ApiError ? err.message : "Google login failed.";
                setError(message);
                return false;
            }
        },
        [applySession, loadProfile, loadWorkspaces]
    );

    const signInWithGooglePopup = useCallback(async () => {
        setError(null);
        let popup: Window | null = null;
        try {
            const start = await apiClient.startGoogleOAuth();
            popup = window.open(
                start.authorization_url,
                "sand-swap-google-oauth",
                "popup=yes,width=520,height=720"
            );
            if (!popup) {
                throw new Error("Popup was blocked by the browser");
            }

            const payload = await new Promise<{
                access_token: string;
                refresh_token: string;
                token_type: string;
            }>((resolve, reject) => {
                const timeout = window.setTimeout(() => {
                    window.removeEventListener("message", listener);
                    reject(new Error("Google sign-in timed out"));
                }, 120000);

                const listener = (event: MessageEvent) => {
                    const data = event.data as {
                        source?: string;
                        access_token?: string;
                        refresh_token?: string;
                        token_type?: string;
                    };
                    if (!data || data.source !== "sand-swap-oauth") {
                        return;
                    }
                    if (!data.access_token || !data.refresh_token) {
                        return;
                    }
                    window.clearTimeout(timeout);
                    window.removeEventListener("message", listener);
                    resolve({
                        access_token: data.access_token,
                        refresh_token: data.refresh_token,
                        token_type: data.token_type || "bearer",
                    });
                };

                window.addEventListener("message", listener);
            });

            applySession(payload);
            await loadProfile();
            await loadWorkspaces();
            try {
                popup.close();
            } catch {
                // noop
            }
            return true;
        } catch (err) {
            const message =
                err instanceof ApiError
                    ? err.message
                    : err instanceof Error
                        ? err.message
                        : "Google login failed.";
            setError(message);
            try {
                popup?.close();
            } catch {
                // noop
            }
            return false;
        }
    }, [applySession, loadProfile, loadWorkspaces]);

    const logout = useCallback(async () => {
        const activeSession = loadAuthSession();
        try {
            await apiClient.logout({
                refresh_token: activeSession?.refreshToken ?? null,
            });
        } catch {
            // Keep client-side logout resilient even if API logout fails.
        }
        clearSession();
    }, [clearSession]);

    useEffect(() => {
        const stored = loadAuthSession();
        if (!stored) {
            apiClient.setAuthToken(null);
            setIsLoading(false);
            return;
        }

        apiClient.setAuthToken(stored.accessToken);
        void loadProfile().finally(() => {
            setIsLoading(false);
        });
    }, [loadProfile]);

    useEffect(() => {
        if (!session?.access_token) {
            setWorkspaces([]);
            setIsWorkspaceLoading(false);
            return;
        }
        void loadWorkspaces();
    }, [loadWorkspaces, session?.access_token]);

    const switchWorkspace = useCallback(
        async (workspaceId: string) => {
            const workspace = await apiClient.switchWorkspace(workspaceId);
            apiClient.setWorkspaceId(workspace.id);
            window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace.id);
            setWorkspaces((previous) =>
                previous.map((item) => ({
                    ...item,
                    is_active: item.id === workspace.id,
                }))
            );
            setProfile((previous) =>
                previous
                    ? {
                        ...previous,
                        project_id: workspace.id,
                    }
                    : previous
            );
            return workspace;
        },
        []
    );

    const createWorkspace = useCallback(
        async (name: string, description = "") => {
            const workspace = await apiClient.createWorkspace({
                name,
                description,
                set_active: true,
            });
            apiClient.setWorkspaceId(workspace.id);
            window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace.id);
            setWorkspaces((previous) => {
                const next = previous.filter((item) => item.id !== workspace.id);
                return [
                    { ...workspace, is_active: true },
                    ...next.map((item) => ({ ...item, is_active: false })),
                ];
            });
            setProfile((previous) =>
                previous
                    ? {
                        ...previous,
                        project_id: workspace.id,
                    }
                    : previous
            );
            return workspace;
        },
        []
    );

    const renameWorkspace = useCallback(async (workspaceId: string, name: string) => {
        const workspace = await apiClient.renameWorkspace(workspaceId, { name });
        setWorkspaces((previous) =>
            previous.map((item) =>
                item.id === workspace.id ? { ...item, name: workspace.name } : item
            )
        );
        return workspace;
    }, []);

    const deleteWorkspace = useCallback(
        async (workspaceId: string) => {
            await apiClient.deleteWorkspace(workspaceId);
            const next = await loadWorkspaces();
            const active = next.find((item) => item.is_active) ?? null;
            apiClient.setWorkspaceId(active?.id ?? null);
            if (active?.id) {
                window.localStorage.setItem(WORKSPACE_STORAGE_KEY, active.id);
            } else {
                window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
            }
            setProfile((previous) =>
                previous
                    ? {
                        ...previous,
                        project_id: active?.id ?? null,
                    }
                    : previous
            );
        },
        [loadWorkspaces]
    );

    const isAuthenticated = useMemo(
        () => Boolean(session?.access_token && profile?.user_id),
        [profile?.user_id, session?.access_token]
    );

    const effectiveUserId = useMemo(() => {
        if (profile?.user_id) {
            return profile.user_id;
        }
        return anonymousSessionId;
    }, [anonymousSessionId, profile?.user_id]);

    return {
        isLoading,
        isAuthenticated,
        error,
        session,
        profile,
        workspaces,
        activeWorkspaceId: profile?.project_id ?? null,
        isWorkspaceLoading,
        anonymousUserId: anonymousSessionId,
        effectiveUserId,
        createWorkspace,
        renameWorkspace,
        deleteWorkspace,
        switchWorkspace,
        loginWithPassword,
        loginWithGoogleCode,
        signInWithGooglePopup,
        loadProfile,
        logout,
    };
};
