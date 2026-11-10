export class AudioPlaybackQueue {
  constructor(createContext, onActivity = () => {}) {
    this.createContext = createContext;
    this.onActivity = onActivity;
    this.context = null;
    this.nextAt = 0;
    this.sources = new Set();
    this.remainder = null;
  }

  appendPcm(bytes, sampleRate) {
    let pcmBytes = bytes;
    if (this.remainder && this.remainder.byteLength > 0) {
      const combined = new Uint8Array(this.remainder.byteLength + bytes.byteLength);
      combined.set(this.remainder, 0);
      combined.set(bytes, this.remainder.byteLength);
      pcmBytes = combined;
      this.remainder = null;
    }
    const remainderLength = pcmBytes.byteLength % 2;
    if (remainderLength > 0) {
      this.remainder = pcmBytes.slice(pcmBytes.byteLength - remainderLength);
      pcmBytes = pcmBytes.subarray(0, pcmBytes.byteLength - remainderLength);
    }
    const count = Math.floor(pcmBytes.byteLength / 2);
    if (!count) return;
    const context = this.context || (this.context = this.createContext());
    const data = new DataView(pcmBytes.buffer, pcmBytes.byteOffset, pcmBytes.byteLength);
    const buffer = context.createBuffer(1, count, sampleRate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < count; i++) samples[i] = data.getInt16(i * 2, true) / 32768;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const at = Math.max(context.currentTime + 0.015, this.nextAt);
    this.nextAt = at + buffer.duration;
    this.sources.add(source);
    this.onActivity(true);
    source.onended = () => {
      this.sources.delete(source);
      if (!this.sources.size) this.onActivity(false);
    };
    try { source.start(at); } catch { /* already started */ }
    void context.resume().catch(() => {});
  }

  interrupt() {
    for (const source of this.sources) {
      try { source.stop(); } catch { /* already stopped */ }
    }
    this.sources.clear();
    this.remainder = null;
    this.nextAt = this.context?.currentTime || 0;
    this.onActivity(false);
  }

  get active() { return this.sources.size > 0; }
}
