export interface StoredAuthSession {
    accessToken: string;
    refreshToken: string;
    tokenType: string;
}

const AUTH_STORAGE_KEY = "sand-swap-auth-session-v1";

export const loadAuthSession = (): StoredAuthSession | null => {
    try {
        const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw) as Partial<StoredAuthSession>;
        if (
            typeof parsed.accessToken !== "string"
            || typeof parsed.refreshToken !== "string"
            || typeof parsed.tokenType !== "string"
        ) {
            return null;
        }
        return {
            accessToken: parsed.accessToken,
            refreshToken: parsed.refreshToken,
            tokenType: parsed.tokenType,
        };
    } catch {
        return null;
    }
};

export const persistAuthSession = (session: StoredAuthSession | null): void => {
    if (session === null) {
        window.localStorage.removeItem(AUTH_STORAGE_KEY);
        return;
    }
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
};
