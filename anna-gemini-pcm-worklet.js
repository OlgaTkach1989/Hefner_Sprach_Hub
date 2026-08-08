class AnnaPcmInputProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.targetRate = 16000
    this.sourceChunkSize = Math.max(1, Math.round(sampleRate / 10))
    this.pending = new Float32Array(this.sourceChunkSize)
    this.pendingLength = 0
  }

  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel) return true

    let offset = 0
    while (offset < channel.length) {
      const available = this.pending.length - this.pendingLength
      const count = Math.min(available, channel.length - offset)
      this.pending.set(channel.subarray(offset, offset + count), this.pendingLength)
      this.pendingLength += count
      offset += count
      if (this.pendingLength === this.pending.length) {
        const pcm = this.downsample(this.pending)
        this.port.postMessage(pcm.buffer, [pcm.buffer])
        this.pendingLength = 0
      }
    }
    return true
  }

  downsample(input) {
    const outputLength = Math.max(1, Math.round((input.length * this.targetRate) / sampleRate))
    const output = new Int16Array(outputLength)
    const ratio = input.length / outputLength
    for (let index = 0; index < outputLength; index += 1) {
      const start = Math.floor(index * ratio)
      const end = Math.max(start + 1, Math.floor((index + 1) * ratio))
      let sum = 0
      for (let sourceIndex = start; sourceIndex < end && sourceIndex < input.length; sourceIndex += 1) {
        sum += input[sourceIndex]
      }
      const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)))
      output[index] = sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767)
    }
    return output
  }
}

registerProcessor("anna-pcm-input", AnnaPcmInputProcessor)

