import type { HealthResponse } from "../../types/api";

interface HealthIndicatorProps {
    health: HealthResponse | null;
    isLoading: boolean;
    error: string | null;
}

export const HealthIndicator = ({
    health,
    isLoading,
    error,
}: HealthIndicatorProps) => {
    if (isLoading) {
        return <span className="health-pill health-pill--loading">Checking API...</span>;
    }

    if (error) {
        return <span className="health-pill health-pill--error">Offline</span>;
    }

    const status = health?.status === "ok" ? "Healthy" : "Unknown";
    return <span className="health-pill health-pill--ok">{status}</span>;
};
