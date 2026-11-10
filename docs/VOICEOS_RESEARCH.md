# VoiceOS public research

Research date: 2026-11-07. Sources reviewed: VoiceOS official website, public interactive demo, and official changelog.

## Publicly documented
- The product presents itself as a voice assistant for Mac and Windows, and promotes dictation plus “voice-to-action” workflows across apps.
- The official site advertises pointing at screen content so the cursor provides context; it gives examples of sending email, creating calendar events, filing tickets, searching, and locating files.
- The official site lists examples/integrations including Gmail, Slack, Linear, Google Docs, Obsidian, Chrome, VS Code, WhatsApp, Outlook, Notion, and others. The page does not establish that every feature is available on every platform or account.
- Public privacy copy says transcripts can be saved locally and audio is not saved in the cloud; optional anonymous diagnostics are described. Treat those as vendor claims, not an independent security audit.
- The public changelog shows ongoing work on Agent Mode, integrations, microphone handling, retries, and Windows media controls. This provides evidence of evolving functionality, not a complete technical specification.
- The browser demo explicitly says it uses browser speech services and is not connected to the production VoiceOS AI engine.

## Marketing or ambiguous
- Productivity multipliers and testimonials are promotional claims, not measured guarantees.
- “Works seamlessly” and broad app lists do not specify API versus UI automation, account prerequisites, platform parity, or exact permissions.
- The product pages do not fully describe agent planning, confirmation rules, rollback, supported action boundaries, retention implementation, model providers, or security architecture.

## Not publicly specified in reviewed sources
- Exact Windows feature parity, supported Windows versions, integration implementation details, authorization scopes, local/cloud model routing, encryption/key management, data retention controls at protocol level, and reliability/latency guarantees.

## Maya decisions
| Public capability | Decision | Reason |
|---|---|---|
| Voice dictation and voice-to-action | Adapt | Prioritize spoken commands and a usable orb/chat fallback, with observable states and explicit confirmations. |
| Cursor/screen context | Adapt | Add only user-triggered screen capture and per-use consent; never continuous capture by default. |
| App integrations | Adapt | Begin with allowlisted local app launching and explicitly scoped tools; do not claim broad integration parity. |
| Local transcript controls/privacy messaging | Adopt | Keep history opt-in/configurable and never persist audio by default; make provider transmission visible. |
| Agent Mode/background follow-ups | Adapt | Defer until safety, cancellation, audit, and opt-in scheduling exist. |
| Marketing productivity claims | Skip | Not independently verifiable or a product requirement. |
| Undocumented automation/security behavior | Skip | No capabilities are assumed beyond public evidence. |

## Sources
- [VoiceOS official product site](https://www.voiceos.com/)
- [VoiceOS public interactive demo](https://www.voiceos.com/demo)
- [VoiceOS official changelog](https://www.voiceos.com/changelog)
