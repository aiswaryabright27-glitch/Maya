# Maya Agent & State Event Schema

Maya broadcasts real-time state and action events over an authenticated Server-Sent Events (SSE) connection and Electron IPC (`maya:conversation-event` and `maya:agent-event`). This contract allows any frontend component or future 3D companion character to respond to Maya's internal state without architectural changes.

---

## 1. Event Transport & Envelope

Every event emitted by Maya follows this JSON envelope:

```json
{
  "eventId": "evt_01J8F...",
  "timestamp": "2026-11-10T00:30:00.000Z",
  "requestId": "req_uuid...",
  "type": "state_change | tool_start | tool_step | tool_complete | confirmation_required | confirmation_resolved | notification",
  "state": "idle | listening | thinking | speaking | executing | waiting_confirmation | interrupted | error | sleeping",
  "emotion": "neutral | happy | thinking | curious | focused | celebratory | apologetic | error",
  "payload": {}
}
```

---

## 2. Agent State Definitions

| State | Description | Typical Emotion Hint | 3D Companion Hook |
|---|---|---|---|
| `idle` | Waiting for user interaction or wake word. | `neutral` | Subtle breathing/hover animation, occasional blink. |
| `listening` | Microphone active, user speech detected above voice gate. | `curious` | Head tilts forward, ear/antenna pulse, green glow. |
| `thinking` | LLM planning or reasoning over instructions. | `thinking` | Eyes look up/aside, gentle side-to-side orbit, blue glow. |
| `speaking` | Generating speech and playing TTS audio chunks. | `happy` / `neutral` | Mouth/viseme sync, expressive nodding, cyan glow. |
| `executing` | Running tools (opening apps, moving files, searching). | `focused` | Typing or working animation, purple/amber indicator. |
| `waiting_confirmation` | Waiting for user approval on a risky/destructive action. | `curious` | Open palms/questioning posture, yellow pulse. |
| `interrupted` | User barged in (voice "stop", hotkey, click). | `apologetic` | Immediate halt, quick recoil to neutral, sound cuts. |
| `error` | Tool failed or network error occurred. | `error` | Head shake, red alert pulse, sympathetic expression. |
| `sleeping` | Quiet hours or focus session enabled. | `neutral` | Eyes closed, slow calm breathing animation. |

---

## 3. Tool & Execution Payloads

### `tool_start`
Emitted when a multi-step plan begins or an individual tool is invoked:
```json
{
  "type": "tool_start",
  "state": "executing",
  "emotion": "focused",
  "payload": {
    "taskId": "task_123",
    "stepIndex": 1,
    "totalSteps": 3,
    "toolName": "apps.open_application",
    "summary": "Opening Visual Studio Code"
  }
}
```

### `confirmation_required`
Emitted when an action requires explicit human confirmation:
```json
{
  "type": "confirmation_required",
  "state": "waiting_confirmation",
  "emotion": "curious",
  "payload": {
    "confirmationId": "conf_789",
    "riskLevel": "destructive",
    "action": "gmail.send_email",
    "preview": {
      "to": ["recruiter@company.com"],
      "subject": "Follow-up on Application",
      "bodySnippet": "Dear Recruiter, Thank you for..."
    },
    "timeoutSeconds": 30
  }
}
```

### `confirmation_resolved`
Emitted once the user approves, edits, rejects, or times out:
```json
{
  "type": "confirmation_resolved",
  "state": "executing",
  "payload": {
    "confirmationId": "conf_789",
    "decision": "approved | rejected | timed_out",
    "medium": "voice | click"
  }
}
```

---

## 4. Subscribing in Frontend or Character Engine

In React / Renderer:
```typescript
window.mayaDesktop.onAgentEvent((event) => {
  console.log(`Agent state: ${event.state}, Emotion: ${event.emotion}`);
  characterController.transitionTo(event.state, event.emotion);
});
```
