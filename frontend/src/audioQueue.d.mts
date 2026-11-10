export class AudioPlaybackQueue {
  constructor(createContext: () => AudioContext, onActivity?: (active: boolean) => void);
  appendPcm(bytes: Uint8Array, sampleRate: number): void;
  interrupt(): void;
  readonly active: boolean;
}
