import React from 'react';
import { createRoot } from 'react-dom/client';
import { AudioPlaybackQueue } from './audioQueue.mjs';
import './style.css';

type Health = { ok: boolean; mode: 'mock' | 'unavailable'; databaseReady: boolean; capabilities: string[] };
type ConversationEvent = { requestId: string; type: string; value?: string; text?: string; message?: string; language?: string; pcm_base64?: string; sample_rate?: number };
type AudioDevice = { deviceId: string; label: string };
declare global {
  interface Window { mayaDesktop: {
    getHealth(): Promise<Health>;
    startConversation(payload: { audioBase64: string; language: string; requestId: string }): void;
    cancelSpeech(requestId: string): Promise<void>;
    onConversationEvent(callback: (event: ConversationEvent) => void): () => void;
    onHotkey(callback: () => void): () => void;
  } }
}

const languageNames: Record<string, string> = { auto: 'Auto · follow speaker', en: 'English', hi: 'Hindi', ml: 'Malayalam', kn: 'Kannada', ta: 'Tamil', te: 'Telugu', bn: 'Bengali', mr: 'Marathi', gu: 'Gujarati', pa: 'Punjabi' };
function mergeAudioChunks(chunks: Float32Array[]): Float32Array {
  const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
  const result = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function wavBase64(samples: Float32Array, sampleRate: number) {
  const pcm = new ArrayBuffer(44 + samples.length * 2), view = new DataView(pcm);
  const write = (offset: number, text: string) => [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)));
  write(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); write(8, 'WAVE'); write(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, 'data'); view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) { const value = Math.max(-1, Math.min(1, samples[i])); view.setInt16(44 + i * 2, value < 0 ? value * 32768 : value * 32767, true); }
  const bytes = new Uint8Array(pcm);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + chunkSize)));
  }
  return btoa(binary);
}

type NoiseProfile = 'crowded' | 'noisy' | 'normal' | 'quiet' | 'custom';
const profileThresholds: Record<NoiseProfile, number> = {
  crowded: 0.055,
  noisy: 0.045,
  normal: 0.030,
  quiet: 0.018,
  custom: 0.055,
};

function App() {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [status, setStatus] = React.useState('Connecting to local service…');
  const [active, setActive] = React.useState(false);
  const [handsFree, setHandsFree] = React.useState(false);
  const [noiseProfile, setNoiseProfile] = React.useState<NoiseProfile>(() => (localStorage.getItem('maya.noiseProfile') as NoiseProfile) || 'normal');
  const [sensitivity, setSensitivity] = React.useState(() => {
    const saved = localStorage.getItem('maya.sensitivity');
    if (saved) return Number(saved);
    const initial = (localStorage.getItem('maya.noiseProfile') as NoiseProfile) || 'normal';
    return profileThresholds[initial] || 0.075;
  });
  const [voiceDetected, setVoiceDetected] = React.useState(false);
  const [language, setLanguage] = React.useState('auto');
  const [transcript, setTranscript] = React.useState('');
  const [reply, setReply] = React.useState('');
  const [privacy, setPrivacy] = React.useState('Microphone is off');
  const [level, setLevel] = React.useState(0);
  const [notice, setNotice] = React.useState('');
  const [devices, setDevices] = React.useState<AudioDevice[]>([]);
  const [deviceId, setDeviceId] = React.useState(() => localStorage.getItem('maya.microphone.deviceId') || '');
  const [assistantSpeaking, setAssistantSpeaking] = React.useState(false);
  const [thinking, setThinking] = React.useState(false);
  const activeRef = React.useRef(false);
  const healthRef = React.useRef<Health | null>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const audioRef = React.useRef<AudioContext | null>(null);
  const highpassRef = React.useRef<BiquadFilterNode | null>(null);
  const lowpassRef = React.useRef<BiquadFilterNode | null>(null);
  const playbackRef = React.useRef<AudioContext | null>(null);
  const playbackQueueRef = React.useRef<AudioPlaybackQueue | null>(null);
  const processorRef = React.useRef<ScriptProcessorNode | null>(null);
  const chunksRef = React.useRef<Float32Array[]>([]);
  const speakingRef = React.useRef(false);
  const loudFramesRef = React.useRef(0);
  const silenceRef = React.useRef(0);
  const pushToTalkRef = React.useRef(false);
  const handsFreeRef = React.useRef(false);
  const sensitivityRef = React.useRef(sensitivity);
  const noiseFloorRef = React.useRef(0.01);
  const noiseProfileRef = React.useRef(noiseProfile);
  const requestRef = React.useRef<string | null>(null);
  const turnStartedRef = React.useRef(0);
  const firstTranscriptRef = React.useRef(false);
  const firstAudioRef = React.useRef(false);
  const assistantSpeakingRef = React.useRef(false);
  const languageRef = React.useRef(language);

  React.useEffect(() => { handsFreeRef.current = handsFree; }, [handsFree]);
  React.useEffect(() => { sensitivityRef.current = sensitivity; }, [sensitivity]);
  React.useEffect(() => { noiseProfileRef.current = noiseProfile; }, [noiseProfile]);
  React.useEffect(() => { languageRef.current = language; }, [language]);
  React.useEffect(() => { void enumerateAudioDevices(); }, []);

  function handleProfileChange(profile: NoiseProfile) {
    setNoiseProfile(profile);
    localStorage.setItem('maya.noiseProfile', profile);
    if (profile !== 'custom') {
      const val = profileThresholds[profile];
      setSensitivity(val);
      sensitivityRef.current = val;
      localStorage.setItem('maya.sensitivity', String(val));
    }
  }

  function handleSensitivityChange(val: number) {
    setSensitivity(val);
    sensitivityRef.current = val;
    setNoiseProfile('custom');
    localStorage.setItem('maya.noiseProfile', 'custom');
    localStorage.setItem('maya.sensitivity', String(val));
  }
  React.useEffect(() => {
    let mounted = true;
    void window.mayaDesktop.getHealth().then((result) => { if (mounted) { healthRef.current = result; setHealth(result); setStatus(result.ok && result.databaseReady ? 'Local service and database ready' : 'Local service unavailable'); } });
    const removeEvents = window.mayaDesktop.onConversationEvent((event) => { if (event.requestId === requestRef.current) handleConversationEvent(event); });
    const removeHotkey = window.mayaDesktop.onHotkey(() => { if (requestRef.current || assistantSpeakingRef.current) interruptMaya(); else void toggleMicrophone(); });
    return () => { mounted = false; removeEvents(); removeHotkey(); void stopMicrophone(); };
  }, []);

  function interruptMaya() {
    const requestId = requestRef.current;
    requestRef.current = null;
    if (requestId) void window.mayaDesktop.cancelSpeech(requestId);
    playbackQueueRef.current?.interrupt();
    assistantSpeakingRef.current = false; setAssistantSpeaking(false); setThinking(false); setNotice('Interrupted. Maya stopped generating and cleared queued audio.');
  }

  function queuePcm(encoded: string, sampleRate: number) {
    if (!playbackQueueRef.current) playbackQueueRef.current = new AudioPlaybackQueue(() => playbackRef.current || (playbackRef.current = new AudioContext({ sampleRate })), (speaking) => { assistantSpeakingRef.current = speaking; setAssistantSpeaking(speaking); });
    const binary = atob(encoded);
    playbackQueueRef.current.appendPcm(Uint8Array.from(binary, (char) => char.charCodeAt(0)), sampleRate);
  }

  function handleConversationEvent(event: ConversationEvent) {
    if (event.type === 'status') setNotice(event.value === 'transcribing' ? 'Transcribing…' : event.value || 'Working…');
    if (event.type === 'mock') { setNotice(event.message || 'Mock mode: speech is not recognized.'); setThinking(false); requestRef.current = null; }
    if (event.type === 'transcript' && event.text) {
      if (!firstTranscriptRef.current) { firstTranscriptRef.current = true; const elapsed = performance.now() - turnStartedRef.current; console.info(`maya first_transcript_ms=${elapsed.toFixed(1)}`); setNotice(`Transcript ready · ${Math.round(elapsed)} ms · generating reply…`); }
      setTranscript((previous) => `${previous}${previous ? '\n' : ''}${event.text}`);
      if (/^(stop|stop maya|cancel|cancel that)[.!\s]*$/i.test(event.text.trim())) { interruptMaya(); return; }
      setNotice(`Heard ${languageNames[event.language || languageRef.current] || 'speech'} · generating reply…`);
    }
    if (event.type === 'assistant_delta' && event.text) setReply((previous) => previous + event.text);
    if (event.type === 'assistant_final' && event.text) setReply(event.text);
    if (event.type === 'audio' && event.pcm_base64) {
      if (!firstAudioRef.current) { firstAudioRef.current = true; const elapsed = performance.now() - turnStartedRef.current; console.info(`maya end_of_speech_to_first_audio_ms=${elapsed.toFixed(1)}`); setNotice(`Maya is speaking · first audio ${Math.round(elapsed)} ms`); }
      queuePcm(event.pcm_base64, event.sample_rate || 24000);
    }
    if (event.type === 'error') { setNotice(event.message || 'Voice request failed.'); setThinking(false); requestRef.current = null; }
    if (event.type === 'done') { requestRef.current = null; setThinking(false); if (!assistantSpeakingRef.current) setNotice('Ready'); }
  }

  async function enumerateAudioDevices() {
    try { const inputs = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === 'audioinput'); setDevices(inputs.map((device, index) => ({ deviceId: device.deviceId, label: device.label || `Microphone ${index + 1}` }))); }
    catch { setDevices([]); }
  }

  async function submitAudio(samples: Float32Array, sampleRate: number) {
    if (samples.length < sampleRate * 0.25) return;
    const power = samples.reduce((sum, value) => sum + value * value, 0) / samples.length;
    if (power < 0.0001) return;
    console.info(`maya segment duration_s=${(samples.length / sampleRate).toFixed(2)} rms=${Math.sqrt(power).toFixed(4)}`);
    if (requestRef.current) interruptMaya();
    setReply(''); setNotice('Transcribing…'); setThinking(true);
    turnStartedRef.current = performance.now(); firstTranscriptRef.current = false; firstAudioRef.current = false;
    const requestId = crypto.randomUUID(); requestRef.current = requestId;
    window.mayaDesktop.startConversation({ audioBase64: wavBase64(samples, sampleRate), language: languageRef.current, requestId });
  }

  async function startMicrophone() {
    if (active) return;
    if (!navigator.mediaDevices?.getUserMedia) { setNotice('Microphone capture is unavailable.'); return; }
    let capturedStream: MediaStream | null = null;
    try {
      const useAgc = true;
      const audio = {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: useAgc,
        ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
      };
      const stream = await navigator.mediaDevices.getUserMedia({ audio }); capturedStream = stream; streamRef.current = stream;
      activeRef.current = true; setActive(true);
      setPrivacy(healthRef.current?.capabilities.includes('speech.stt') ? 'VOICE ISOLATION ACTIVE · only speech above gate is captured' : healthRef.current ? 'VOICE ISOLATION ACTIVE · local mock mode' : 'VOICE ISOLATION ACTIVE · checking provider');
      const context = new AudioContext({ sampleRate: 16000 });
      audioRef.current = context;

      const source = context.createMediaStreamSource(stream);

      // Voice-band frequency filter: 120 Hz highpass cuts rumble/AC/fans, 3600 Hz lowpass cuts hiss/clicks
      const highpass = context.createBiquadFilter();
      highpass.type = 'highpass';
      highpass.frequency.value = 120;
      highpass.Q.value = 1.0;
      highpassRef.current = highpass;

      const lowpass = context.createBiquadFilter();
      lowpass.type = 'lowpass';
      lowpass.frequency.value = 3600;
      lowpass.Q.value = 1.0;
      lowpassRef.current = lowpass;

      const processor = context.createScriptProcessor(1024, 1, 1);
      const mute = context.createGain();
      mute.gain.value = 0;

      if (!playbackRef.current || playbackRef.current.state === 'closed') playbackRef.current = new AudioContext({ sampleRate: 24000 });
      playbackQueueRef.current = new AudioPlaybackQueue(() => playbackRef.current!, (speaking) => { assistantSpeakingRef.current = speaking; setAssistantSpeaking(speaking); });
      void playbackRef.current.resume().catch(() => {});

      processorRef.current = processor;
      chunksRef.current = []; speakingRef.current = false; loudFramesRef.current = 0; silenceRef.current = 0;
      noiseFloorRef.current = 0.01;

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0), copy = new Float32Array(input);
        let sum = 0; for (const sample of input) sum += sample * sample;
        const rms = Math.sqrt(sum / input.length);

        if (rms < noiseFloorRef.current) {
          noiseFloorRef.current = noiseFloorRef.current * 0.90 + rms * 0.10;
        } else {
          noiseFloorRef.current = noiseFloorRef.current * 0.998 + rms * 0.002;
        }

        const isVoice = rms >= sensitivityRef.current && rms >= noiseFloorRef.current * 1.5;
        setVoiceDetected(isVoice);
        setLevel(Math.min(100, rms * 500));

        // No attenuation: modifying samples corrupts speech for STT.

        if (!handsFreeRef.current) {
          if (pushToTalkRef.current) chunksRef.current.push(copy);
          return;
        }
        if (assistantSpeakingRef.current) { loudFramesRef.current = 0; return; }
        const frameMs = (input.length / context.sampleRate) * 1000;

        if (isVoice) {
          loudFramesRef.current += 1;
          if (!speakingRef.current && loudFramesRef.current * frameMs < 150) return;
          if (assistantSpeakingRef.current || requestRef.current) interruptMaya();
          speakingRef.current = true; silenceRef.current = 0; chunksRef.current.push(copy);
        } else {
          loudFramesRef.current = 0;
          if (speakingRef.current) {
            chunksRef.current.push(copy); silenceRef.current += input.length;
            if (silenceRef.current > context.sampleRate * 0.75) {
              const segment = mergeAudioChunks(chunksRef.current);
              chunksRef.current = []; speakingRef.current = false; loudFramesRef.current = 0; silenceRef.current = 0; void submitAudio(segment, context.sampleRate);
            }
          }
        }
      };

      source.connect(highpass);
      highpass.connect(lowpass);
      lowpass.connect(processor);
      processor.connect(mute);
      mute.connect(context.destination);

      setNotice(handsFreeRef.current ? 'Voice isolation active · speak into mic.' : 'Push to talk, or enable hands-free VAD.');
      await enumerateAudioDevices();
    } catch {
      capturedStream?.getTracks().forEach((track) => track.stop());
      if (streamRef.current === capturedStream) streamRef.current = null;
      processorRef.current?.disconnect(); processorRef.current = null;
      highpassRef.current?.disconnect(); highpassRef.current = null;
      lowpassRef.current?.disconnect(); lowpassRef.current = null;
      await audioRef.current?.close().catch(() => {}); audioRef.current = null;
      await playbackRef.current?.close().catch(() => {}); playbackRef.current = null; playbackQueueRef.current = null;
      activeRef.current = false; setActive(false); setVoiceDetected(false); setPrivacy('Microphone is off');
      setNotice('Microphone permission was denied or the selected device is unavailable.');
    }
  }

  async function stopMicrophone() {
    if (!active && !streamRef.current) return;
    if (requestRef.current) interruptMaya();
    processorRef.current?.disconnect(); processorRef.current = null;
    highpassRef.current?.disconnect(); highpassRef.current = null;
    lowpassRef.current?.disconnect(); lowpassRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null;
    await audioRef.current?.close(); audioRef.current = null;
    activeRef.current = false; setActive(false); setHandsFree(false); pushToTalkRef.current = false; setLevel(0); setVoiceDetected(false); setPrivacy('Microphone is off');
  }

  async function toggleMicrophone() { if (activeRef.current) await stopMicrophone(); else await startMicrophone(); }
  function pushToTalkStart() { if (!active) return; void playbackRef.current?.resume().catch(() => {}); if (assistantSpeakingRef.current) interruptMaya(); pushToTalkRef.current = true; speakingRef.current = true; chunksRef.current = []; }
  function pushToTalkEnd() { pushToTalkRef.current = false; if (!audioRef.current || handsFreeRef.current || !chunksRef.current.length) return; const samples = mergeAudioChunks(chunksRef.current); chunksRef.current = []; speakingRef.current = false; void submitAudio(samples, audioRef.current.sampleRate); }

  const mock = !health?.capabilities.includes('speech.stt') || !health.capabilities.includes('llm.stream');
  return <main>
    <div className="badge">{mock ? 'MOCK MODE · PROVIDER KEY MISSING' : 'LIVE SPEECH + LLM'}</div>
    <div className={`scene ${active ? 'listening' : ''} ${thinking ? 'thinking' : ''} ${assistantSpeaking ? 'talking' : ''}`} aria-label={assistantSpeaking ? 'Maya is speaking' : thinking ? 'Maya is thinking' : active ? 'Microphone active' : 'Maya idle'}>
      <div className="robot"><i className="eye left" /><i className="eye right" /><i className="mouth" /></div>
      <div className="desk" />
    </div>
    <h1>Hi, I’m Maya.</h1><p className="sub">{status}</p>
    <label className="language">Conversation language
      <select value={language} onChange={(event) => setLanguage(event.target.value)}>{Object.entries(languageNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select>
    </label>
    <label className="language">Voice isolation
      <select value={noiseProfile} onChange={(event) => handleProfileChange(event.target.value as NoiseProfile)}>
        <option value="crowded">🛡️ Strict · Crowded / Noisy house (direct voice only)</option>
        <option value="noisy">🔊 Moderate · House noise & fans filtered</option>
        <option value="normal">🎙️ Normal · Standard room</option>
        <option value="quiet">🤫 Quiet · High sensitivity</option>
        <option value="custom">⚙️ Custom voice gate</option>
      </select>
    </label>
    <label className="language">Microphone
      <select disabled={active} value={deviceId} onChange={(event) => { setDeviceId(event.target.value); localStorage.setItem('maya.microphone.deviceId', event.target.value); }}><option value="">System default</option>{devices.map((device) => <option value={device.deviceId} key={device.deviceId}>{device.label}</option>)}</select>
    </label>
    <div className="controls"><button onClick={() => void toggleMicrophone()}>{active ? 'Turn microphone off' : 'Enable microphone'}</button><button className="secondary" disabled={!active} onClick={() => setHandsFree((value) => !value)}>{handsFree ? 'Hands-free on' : 'Enable hands-free'}</button></div>
    <button className="push" disabled={!active || handsFree} onPointerDown={pushToTalkStart} onPointerUp={pushToTalkEnd} onPointerLeave={pushToTalkEnd} onKeyDown={(event) => { if (event.key === ' ' && !event.repeat) pushToTalkStart(); }} onKeyUp={(event) => { if (event.key === ' ') pushToTalkEnd(); }}>Hold to talk</button>
    <label className="sensitivity">Voice gate threshold
      <input type="range" min="0.01" max="0.15" step="0.005" value={sensitivity} onChange={(event) => handleSensitivityChange(Number(event.target.value))} />
      <span>{Math.round(sensitivity * 1000)}</span>
    </label>
    <progress className={`meter ${voiceDetected ? 'voice-active' : ''}`} aria-label={`Microphone level ${Math.round(level)} percent`} value={level} max={100} />
    <div className={`gate-status ${voiceDetected ? 'voice-active' : ''}`}>
      {active ? (voiceDetected ? '● Voice detected' : (level > 4 ? '○ Background sound blocked' : '○ Listening for your voice')) : 'Microphone idle'}
    </div>
    <p className={active ? 'privacy active-privacy' : 'privacy'}>● {privacy}</p>
    {requestRef.current || assistantSpeaking ? <button className="interrupt" onClick={interruptMaya}>Stop Maya</button> : null}
    {notice && <p className="note">{notice}</p>}
    <div className="transcript" aria-live="polite"><strong>You said</strong><pre>{transcript || 'Your transcript will appear here.'}</pre><strong>Maya</strong><pre>{reply || 'Maya’s response will appear here.'}</pre></div>
    <p className="note">Ctrl+Space interrupts or toggles the microphone. Audio is not saved by Maya.</p>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
