# Maya

Maya is a voice-first Windows assistant in development. The current app is a local Electron/React preview with a FastAPI health endpoint. Speech capture and computer control are not implemented.

## Development
Prerequisites: Node.js LTS with npm, Python 3.11+.

1. Create `backend/.venv` and install `backend/requirements.txt`.
2. Run `npm ci`.
3. Run `npm run dev`. Electron starts the backend, waits for authenticated database health, then opens the renderer.
4. Run `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build` for the Phase 1 checks.
5. `npm run package` creates a Windows installer, but a separate Python installation is currently required to run the backend from that package.

The UI and backend clearly identify **MOCK MODE**. No audio is recorded or transmitted by this foundation. The backend's temporary token, port, settings, database, and logs stay outside the renderer.

## Current limits
Speech, Gnani, LLM, desktop actions, permission confirmation, and 3D model loading remain unimplemented. See `docs/IMPLEMENTATION_PLAN.md` for status.
