# Model integration

The user's `maya.glb` is user-owned and must never be generated, overwritten, edited, or deleted by Maya. Place it at `frontend/public/models/maya.glb`; a placeholder, if needed, must use a distinct filename or be drawn in code. A future Settings file picker should store the selected absolute path without modifying the source.

## Blender export
1. Select the character and choose File → Export → glTF 2.0.
2. Select Format: glTF Binary (`.glb`); apply transforms and verify the character faces the expected forward direction (+Y up in glTF).
3. Include mesh, materials, and required textures. Enable animations and export named Actions/NLA tracks.
4. Prefer concise state names: `Idle`, `Listening`, `Thinking`, `Speaking`, `Executing`, `Waiting`, `Interrupted`, `Error`, `Sleeping`. Optional shape keys may use `viseme_*`, `blink`, and `smile`.
5. Keep geometry and textures modest for an always-on desktop overlay; test on the target Windows GPU.

When a loader is implemented it must validate file size/format, load read-only, dispose replaced GPU resources, report missing clips in Settings/Debug, and fall back to a separate placeholder. Compression support and live clip mapping are not implemented yet.
