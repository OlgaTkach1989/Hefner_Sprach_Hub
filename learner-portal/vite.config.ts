import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const basePath = env.VITE_ONLINE_STUDENT_BASE_PATH || "/";

  return {
    base: basePath,
    plugins: [react()],
    server: {
      port: 5180
    }
  };
});
