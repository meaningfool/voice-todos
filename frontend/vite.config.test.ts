import { describe, expect, it, vi } from "vitest";

async function loadConfig(env: NodeJS.ProcessEnv) {
  vi.resetModules();
  vi.stubEnv("WS_BACKEND", env.WS_BACKEND);
  vi.stubEnv("BACKEND_PORT", env.BACKEND_PORT);
  vi.stubEnv("CLOUDFLARE_PORT", env.CLOUDFLARE_PORT);

  return await import("./vite.config");
}

describe("vite websocket backend selection", () => {
  it("routes /ws to the FastAPI backend when WS_BACKEND=fastapi", async () => {
    const { default: config } = await loadConfig({
      WS_BACKEND: "fastapi",
      BACKEND_PORT: "8123",
    });

    expect(config.server?.proxy?.["/ws"]).toMatchObject({
      target: "ws://localhost:8123",
      ws: true,
    });
  });

  it("routes /ws to the Cloudflare backend when WS_BACKEND=cloudflare", async () => {
    const { default: config } = await loadConfig({
      WS_BACKEND: "cloudflare",
      CLOUDFLARE_PORT: "8899",
    });

    expect(config.server?.proxy?.["/ws"]).toMatchObject({
      target: "ws://localhost:8899",
      ws: true,
    });
  });

  it("rejects unsupported WS_BACKEND values clearly", async () => {
    await expect(loadConfig({ WS_BACKEND: "bogus" })).rejects.toThrow(
      "Unsupported WS_BACKEND: bogus"
    );
  });
});
