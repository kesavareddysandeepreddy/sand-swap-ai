import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UploadProgressBar } from "./UploadProgressBar";

describe("UploadProgressBar", () => {
    it("renders progress and eta", () => {
        render(<UploadProgressBar progressPercent={40} remaining={6} eta="2026-01-01T01:00:00+00:00" />);

        expect(screen.getByText("Progress 40%") || screen.getByText("Progress 40")).toBeInTheDocument();
        expect(screen.getByText("Remaining 6")).toBeInTheDocument();
        expect(screen.getByText(/ETA/)).toBeInTheDocument();
    });
});
