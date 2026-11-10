# Architecture

Phase 1 trust boundary: Electron main owns window lifecycle and backend supervision; preload exposes one fixed typed health method; React renderer has no Node integration. FastAPI binds to loopback and owns config validation, SQLite migrations, and redacted logs. On each launch Electron generates a random port and bearer token. Backend health is authenticated by main and only sanitized health fields cross IPC. The current product remains mock mode and has no computer-use tools.

Future conversation flow: capture only while visibly active → provider STT → language/intent routing → permission check → optional confirmation → execution → observation → concise spoken and visual result. Screen capture is user-triggered, with per-use cloud consent. Audio is not persisted by default.
