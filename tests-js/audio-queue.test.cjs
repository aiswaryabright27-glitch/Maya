const test = require('node:test');
const assert = require('node:assert/strict');
const queueModule = import('../frontend/src/audioQueue.mjs');

function fakeContext() {
  const context = {
    currentTime: 10,
    destination: {},
    createBuffer(_channels, length, rate) {
      return { duration: length / rate, getChannelData: () => new Float32Array(length) };
    },
    createBufferSource() {
      const source = { start: (at) => { source.startedAt = at; }, stop: () => { source.stopped = true; }, connect() {} };
      context.sources.push(source);
      return source;
    },
    resume: async () => {},
    sources: [],
  };
  return context;
}

test('PCM playback schedules successive chunks without gaps', async () => {
  const { AudioPlaybackQueue } = await queueModule;
  const context = fakeContext();
  const queue = new AudioPlaybackQueue(() => context);
  queue.appendPcm(new Uint8Array(4800), 24000);
  queue.appendPcm(new Uint8Array(2400), 24000);
  await new Promise(setImmediate);
  assert.equal(context.sources[0].startedAt, 10.015);
  assert.equal(context.sources[1].startedAt, 10.115);
});

test('barge-in stops all scheduled audio and clears the queue', async () => {
  const { AudioPlaybackQueue } = await queueModule;
  const context = fakeContext();
  const activeChanges = [];
  const queue = new AudioPlaybackQueue(() => context, (active) => activeChanges.push(active));
  queue.appendPcm(new Uint8Array(4800), 24000);
  queue.appendPcm(new Uint8Array(2400), 24000);
  await new Promise(setImmediate);
  queue.interrupt();
  assert.deepEqual(context.sources.map((source) => source.stopped), [true, true]);
  assert.equal(queue.active, false);
  assert.equal(activeChanges.at(-1), false);
});
