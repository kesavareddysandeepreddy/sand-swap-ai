const ANONYMOUS_SESSION_KEY = "sand-swap-anonymous-session-id-v1";

const createAnonymousSessionId = (): string => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
        return `anon-${crypto.randomUUID()}`;
    }
    const random = Math.random().toString(36).slice(2);
    return `anon-${Date.now().toString(36)}-${random}`;
};

export const getAnonymousSessionId = (): string => {
    const existing = window.localStorage.getItem(ANONYMOUS_SESSION_KEY)?.trim();
    if (existing) {
        return existing;
    }
    const created = createAnonymousSessionId();
    window.localStorage.setItem(ANONYMOUS_SESSION_KEY, created);
    return created;
};

export const rotateAnonymousSessionId = (): string => {
    const next = createAnonymousSessionId();
    window.localStorage.setItem(ANONYMOUS_SESSION_KEY, next);
    return next;
};
