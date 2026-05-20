class LiveSttProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 2048;
    this.pending = new Float32Array(this.bufferSize);
    this.pendingLength = 0;
  }

  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];
    if (!channel || channel.length === 0) {
      return true;
    }

    let readIndex = 0;
    while (readIndex < channel.length) {
      const remaining = this.bufferSize - this.pendingLength;
      const available = channel.length - readIndex;
      const chunkLength = Math.min(remaining, available);
      this.pending.set(channel.subarray(readIndex, readIndex + chunkLength), this.pendingLength);
      this.pendingLength += chunkLength;
      readIndex += chunkLength;

      if (this.pendingLength >= this.bufferSize) {
        this.port.postMessage({ samples: this.pending.slice(0) });
        this.pendingLength = 0;
      }
    }

    return true;
  }
}

registerProcessor("live-stt-processor", LiveSttProcessor);
