# Troubleshooting

- **Frontend/API will not start:** confirm Node.js LTS and Python 3.11+ are installed and dependencies have been installed.
- **No speech:** this scaffold has no speech capture or provider implementation. The visible MOCK MODE label is expected.
- **Gnani setup:** verify account entitlement and consult current official endpoint/auth documentation; this project intentionally does not guess API details.
- **Model missing:** the companion/GLB loader is not implemented yet; the project does not create or modify `maya.glb`.
- For diagnostics, share only logs after reviewing them for personal information. Secret-safe diagnostics export is planned, not implemented.
