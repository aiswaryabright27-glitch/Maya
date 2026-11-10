# Manual test checklist

Foundation and voice core:
- [ ] Start the desktop shell, backend, and frontend with `npm run dev`.
- [ ] Confirm mock speech clearly says it does not recognize audio.
- [ ] With no Gnani key, explicitly enable microphone and confirm the active indicator; disable and confirm tracks stop.
- [ ] Check push-to-talk, VAD sensitivity, level meter, Ctrl+Space, and device behavior on Windows.
- [ ] With a configured key and approved account, check REST STT and streamed TTS; verify language/voice choices and measure first partial transcript and first audio.
- [ ] Confirm no transcript/audio is persisted by the voice path and logs contain no key or speech content.

Future Windows checks:
- [ ] Verify Ctrl+Space and Caps Lock behavior without changing Caps Lock state.
- [ ] Verify microphone indicator during capture and immediate stop behavior.
- [ ] Test English, Hindi, Malayalam, Kannada, Tamil, Telugu, Bengali, Marathi, Gujarati, Punjabi, romanized and mixed speech against verified provider entitlements.
- [ ] Confirm risky file/message/system actions show exact parameters and require approval.
- [ ] Confirm screen capture occurs only on request and cloud upload asks per-use consent.
- [ ] Load user-owned `maya.glb` read-only and exercise fallback using the distinct placeholder.
- [ ] Confirm startup, tray, multi-monitor, hidden/minimized behavior, and packaged build.
