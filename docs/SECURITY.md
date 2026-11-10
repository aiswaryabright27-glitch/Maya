# Security

Phase 1 status: the Electron main process launches the backend with a random token and random loopback port; all backend routes require that token. The main process validates the renderer URL and IPC main-frame sender, and preload exposes only a fixed health query. The backend validates environment settings, binds only to 127.0.0.1, runs in mock mode, and writes rotating logs through a redaction filter. This is a foundation, not a production-safe desktop agent.

Remaining before computer use: OS credential storage, central backend permission engine, exact-action confirmation for risky operations, cancellation, per-tool audit log, path and symlink protection, and prompt-injection separation for retrieved content. Secrets must never reach renderer, logs, or LLM prompts.

Planned privacy defaults for later phases: risky capabilities off by default, screen sharing only on request with per-use cloud consent, and no audio persistence by default. Phase 1 has no microphone or screen capture.
