import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
    plugins: [react()],

    server: {
        host: "0.0.0.0",
        allowedHosts: [
            "ai.testlabs.co.in",
            "localhost",
            "127.0.0.1",
        ],
    },
});