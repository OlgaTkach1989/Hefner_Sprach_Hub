import { createAnnaLiveSession, type AnnaLiveSession } from "../../api/onlineApi"

type ChatLanguage = "de-DE" | "uk-UA" | "ru-RU"

type GeminiLiveCallbacks = {
  onAudioEnd?: () => void
  onAudioStart?: () => void
  onError?: (error: Error) => void
  onInputTranscript?: (text: string) => void
  onOutputTranscript?: (text: string) => void
  onReady?: (session: AnnaLiveSession) => void
  onStatus?: (status: string) => void
  onTurnComplete?: () => void
}

type GeminiLiveOptions = {
  language: ChatLanguage
  lessonTitle?: string
  level: string
  voice?: string
}

type AudioWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext
}

const OUTPUT_SAMPLE_RATE = 24000
const PLAYBACK_LEAD_SECONDS = 0.045
const PLAYBACK_DRAIN_MS = 300

export class AnnaGeminiLiveClient {
  private audioContext: AudioContext | null = null
  private callbacks: GeminiLiveCallbacks
  private inputNode: AudioWorkletNode | null = null
  private inputSink: GainNode | null = null
  private inputSource: MediaStreamAudioSourceNode | null = null
  private manualClose = false
  private mediaStream: MediaStream | null = null
  private nextPlaybackTime = 0
  private outputGain: GainNode | null = null
  private outputSources = new Set<AudioBufferSourceNode>()
  private socket: WebSocket | null = null
  private turnCompleteTimer = 0

  constructor(callbacks: GeminiLiveCallbacks = {}) {
    this.callbacks = callbacks
  }

  get connected() {
    return this.socket?.readyState === WebSocket.OPEN
  }

  async connect(options: GeminiLiveOptions) {
    if (this.socket) return
    this.manualClose = false
    this.callbacks.onStatus?.("Gemini Live wird verbunden")
    const session = await createAnnaLiveSession(options)
    await this.initializeAudio()

    const socket = new WebSocket(`${session.websocketUrl}?access_token=${encodeURIComponent(session.clientSecret)}`)
    this.socket = socket
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify(session.initialMessage))
      this.callbacks.onStatus?.(`${session.voice} · ${session.model}`)
      this.callbacks.onReady?.(session)
    })
    socket.addEventListener("message", (event) => {
      this.handleMessage(event).catch((error) => this.callbacks.onError?.(asError(error)))
    })
    socket.addEventListener("error", () => this.callbacks.onError?.(new Error("Gemini Live WebSocket error")))
    socket.addEventListener("close", () => {
      this.socket = null
      this.clearOutput()
      if (!this.manualClose) this.callbacks.onError?.(new Error("Gemini Live disconnected"))
      this.callbacks.onStatus?.("offline")
    })

    await new Promise<void>((resolve, reject) => {
      const cleanup = () => {
        socket.removeEventListener("open", handleOpen)
        socket.removeEventListener("error", handleError)
      }
      const handleOpen = () => {
        cleanup()
        resolve()
      }
      const handleError = () => {
        cleanup()
        reject(new Error("Gemini Live WebSocket error"))
      }
      socket.addEventListener("open", handleOpen)
      socket.addEventListener("error", handleError)
    })
  }

  sendText(text: string) {
    const clean = text.trim()
    if (!clean || !this.connected) return false
    this.socket?.send(JSON.stringify({ realtimeInput: { text: clean } }))
    return true
  }

  async disconnect() {
    this.manualClose = true
    this.socket?.close(1000, "client disconnect")
    this.socket = null
    this.clearOutput()
    this.inputSource?.disconnect()
    this.inputNode?.disconnect()
    this.inputSink?.disconnect()
    this.outputGain?.disconnect()
    this.mediaStream?.getTracks().forEach((track) => track.stop())
    await this.audioContext?.close().catch(() => undefined)
    this.audioContext = null
    this.inputNode = null
    this.inputSink = null
    this.inputSource = null
    this.mediaStream = null
    this.outputGain = null
  }

  private async initializeAudio() {
    const audioWindow = window as AudioWindow
    const AudioContextClass = audioWindow.AudioContext || audioWindow.webkitAudioContext
    if (!AudioContextClass) throw new Error("Web Audio API is unavailable")

    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        autoGainControl: true,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    this.audioContext = new AudioContextClass()
    await this.audioContext.resume()
    await this.audioContext.audioWorklet.addModule("/anna-gemini-pcm-worklet.js")

    this.inputSource = this.audioContext.createMediaStreamSource(this.mediaStream)
    this.inputNode = new AudioWorkletNode(this.audioContext, "anna-pcm-input")
    this.inputSink = this.audioContext.createGain()
    this.inputSink.gain.value = 0
    this.inputNode.port.addEventListener("message", (event) => this.sendAudio(event.data))
    this.inputNode.port.start()
    this.inputSource.connect(this.inputNode).connect(this.inputSink).connect(this.audioContext.destination)

    this.outputGain = this.audioContext.createGain()
    this.outputGain.connect(this.audioContext.destination)
  }

  private sendAudio(buffer: ArrayBuffer) {
    if (!this.connected) return
    const bytes = new Uint8Array(buffer)
    this.socket?.send(JSON.stringify({
      realtimeInput: {
        audio: {
          data: bytesToBase64(bytes),
          mimeType: "audio/pcm;rate=16000",
        },
      },
    }))
  }

  private async handleMessage(event: MessageEvent) {
    const raw = event.data instanceof Blob ? await event.data.text() : String(event.data)
    const message = JSON.parse(raw)
    if (message.error) {
      throw new Error(String(message.error.message || message.error.status || "Gemini Live error"))
    }
    if (message.setupComplete) this.callbacks.onStatus?.("Gemini Live bereit")

    const content = message.serverContent
    if (!content) return
    if (content.interrupted) this.clearOutput()
    if (content.inputTranscription?.text) {
      this.callbacks.onInputTranscript?.(content.inputTranscription.text.trim())
    }
    if (content.outputTranscription?.text) {
      this.callbacks.onOutputTranscript?.(content.outputTranscription.text.trim())
    }
    for (const part of content.modelTurn?.parts || []) {
      const inline = part.inlineData
      if (inline?.data && String(inline.mimeType || "").startsWith("audio/")) {
        this.queueAudio(inline.data)
      }
    }
    if (content.turnComplete) this.finishTurnAfterPlayback()
  }

  private queueAudio(base64: string) {
    if (!this.audioContext || !this.outputGain) return
    if (this.audioContext.state === "suspended") this.audioContext.resume().catch(() => undefined)
    const bytes = base64ToBytes(base64)
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    const samples = new Float32Array(Math.floor(bytes.byteLength / 2))
    for (let index = 0; index < samples.length; index += 1) {
      samples[index] = view.getInt16(index * 2, true) / 32768
    }

    const buffer = this.audioContext.createBuffer(1, samples.length, OUTPUT_SAMPLE_RATE)
    buffer.copyToChannel(samples, 0)
    const source = this.audioContext.createBufferSource()
    source.buffer = buffer
    source.connect(this.outputGain)
    const now = this.audioContext.currentTime
    const startAt = Math.max(now + PLAYBACK_LEAD_SECONDS, this.nextPlaybackTime)
    this.nextPlaybackTime = startAt + buffer.duration
    this.outputSources.add(source)
    source.addEventListener("ended", () => {
      this.outputSources.delete(source)
      source.disconnect()
    })
    source.start(startAt)
    this.callbacks.onAudioStart?.()
  }

  private finishTurnAfterPlayback() {
    window.clearTimeout(this.turnCompleteTimer)
    const remaining = this.audioContext ? Math.max(0, this.nextPlaybackTime - this.audioContext.currentTime) : 0
    this.turnCompleteTimer = window.setTimeout(() => {
      this.callbacks.onAudioEnd?.()
      this.callbacks.onTurnComplete?.()
    }, Math.ceil(remaining * 1000) + PLAYBACK_DRAIN_MS)
  }

  private clearOutput() {
    window.clearTimeout(this.turnCompleteTimer)
    for (const source of this.outputSources) {
      try {
        source.stop()
      } catch {
        // Source may already be stopped.
      }
    }
    this.outputSources.clear()
    this.nextPlaybackTime = this.audioContext?.currentTime || 0
    this.callbacks.onAudioEnd?.()
  }
}

const bytesToBase64 = (bytes: Uint8Array) => {
  let binary = ""
  const chunkSize = 0x8000
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize))
  }
  return btoa(binary)
}

const base64ToBytes = (value: string) => {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

const asError = (value: unknown) => value instanceof Error ? value : new Error(String(value))

