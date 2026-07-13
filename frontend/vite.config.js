import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), "");
    return {
        plugins: [react()],
        server: {
            host: "0.0.0.0",
            allowedHosts: [
                "ai.testlabs.co.in",
                "localhost",
                "127.0.0.1",
            ],
            proxy: {
                "/api": {
                    target: env.BACKEND_URL || "http://localhost:8007",
                    changeOrigin: true,
                    rewrite: function (path) { return path.replace(/^\/api/, ""); },
                },
            },
        },
    };
});
