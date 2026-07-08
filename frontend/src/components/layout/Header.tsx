import { HealthIndicator } from "../status/HealthIndicator";
import type { HealthResponse } from "../../types/api";

interface HeaderProps {
  health: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
}

export const Header = ({ health, healthLoading, healthError }: HeaderProps) => {
  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">SandSwap AI</p>
        <h1 className="title">Local Chat Console</h1>
      </div>
      <div className="header-meta">
        <HealthIndicator health={health} isLoading={healthLoading} error={healthError} />
      </div>
    </header>
  );
};
