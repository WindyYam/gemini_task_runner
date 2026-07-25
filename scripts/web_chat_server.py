import argparse
import json
import re
import socket
import ssl
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from multiprocessing.connection import Client

DEFAULT_CONFIG = {
    "ai_name": "Jarvis",
    "web_default_prefix": "Guest",
    "web_ipc_host": "127.0.0.1",
    "web_ipc_port": 8766,
    "web_ipc_auth": "gvc-web-ipc-key",
    "web_ws_base_url": "",
    "web_audio_ws_tls_verify": False,
    "web_audio_ws_tls_server_name": "",
  "web_tls_enabled": False,
  "web_tls_certfile": "",
  "web_tls_keyfile": "",
}


def parse_bool(value):
  if isinstance(value, bool):
    return value
  if value is None:
    return False
  text = str(value).strip().lower()
  return text in ("1", "true", "yes", "on")


def load_config(config_path: str):
    config = dict(DEFAULT_CONFIG)
    path = Path(config_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            config.update(data)
    return config


class WebChatService:
    def __init__(
        self,
        config: dict,
        default_prefix: str | None = None,
        ipc_host: str | None = None,
        ipc_port: int | None = None,
        ipc_auth: str | None = None,
        ws_port: int | None = None,
    ):
        self.config = config
        self.ai_name = str(config.get("ai_name") or DEFAULT_CONFIG["ai_name"])
        self.default_prefix = self.sanitize_prefix(default_prefix or config.get("web_default_prefix") or "Guest")
        self.ipc_host = str(ipc_host or config.get("web_ipc_host") or "127.0.0.1").strip()
        self.ipc_port = int(ipc_port or config.get("web_ipc_port") or 8766)
        self.ipc_auth = str(ipc_auth or config.get("web_ipc_auth") or "gvc-web-ipc-key").strip().encode("utf-8")
        self.ws_port = int(ws_port or config.get("web_audio_ws_port") or 8790)
        ws_host = str(config.get("web_audio_ws_host") or "127.0.0.1").strip()
        if ws_host in ("", "0.0.0.0", "::"):
          ws_host = "127.0.0.1"
        self.ws_upstream_host = ws_host
        self.ws_upstream_port = self.ws_port
        self.ws_upstream_tls = parse_bool(config.get("web_audio_ws_tls_enabled")) or parse_bool(config.get("web_tls_enabled"))
        self.ws_upstream_tls_verify = parse_bool(config.get("web_audio_ws_tls_verify"))
        self.ws_upstream_server_name = str(config.get("web_audio_ws_tls_server_name") or "").strip()

    @staticmethod
    def sanitize_prefix(prefix: str):
        text = re.sub(r"[^A-Za-z0-9 _-]", "", str(prefix or "")).strip()
        return text if text else "Guest"

    def _send_ipc(self, payload: dict):
        conn = Client((self.ipc_host, self.ipc_port), authkey=self.ipc_auth)
        try:
            conn.send(payload)
            response = conn.recv()
            if not isinstance(response, dict):
                return {"ok": False, "error": "Invalid backend response"}
            return response
        finally:
            conn.close()

    def reset(self, session_id: str):
        response = self._send_ipc({"type": "reset", "session_id": str(session_id or "default")})
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "Reset failed")

    def chat(self, session_id: str, prefix: str, message: str, speak_bot_voice: bool = False):
        user_prefix = self.sanitize_prefix(prefix or self.default_prefix)
        response = self._send_ipc(
            {
                "type": "chat",
                "session_id": str(session_id or "default"),
                "prefix": user_prefix,
                "message": message.strip(),
          "speak_bot_voice": bool(speak_bot_voice),
            }
        )
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "Backend request failed")

        return {"reply": str(response.get("reply") or ""), "prefix": user_prefix}


HTML_PAGE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Voice Companion Web Chat</title>
  <style>
    :root {
      --bg-a: #f6f2ea;
      --bg-b: #d7e4f5;
      --panel: #fffdf8;
      --ink: #1b222e;
      --muted: #6d7789;
      --accent: #008a6e;
      --accent-2: #dd5f2a;
      --line: #d9dde5;
    }
    html, body {
      width: 100%;
      height: 100%;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: \"Segoe UI\", Tahoma, sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, #fff6d8 0%, rgba(255,246,216,0) 35%),
                  linear-gradient(140deg, var(--bg-a), var(--bg-b));
      overflow: hidden;
    }
    .app {
      width: 100%;
      max-width: none;
      height: 100dvh;
      border-radius: 0;
      background: color-mix(in srgb, var(--panel) 92%, white 8%);
      border: 1px solid var(--line);
      box-shadow: 0 20px 40px rgba(27, 34, 46, 0.12);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
    }
    .top {
      display: grid;
      gap: 12px;
      grid-template-columns: 1fr auto auto auto;
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, rgba(255,255,255,0.75), rgba(255,255,255,0.35));
    }
    .top input[type=\"text\"] {
      width: 100%;
      min-width: 160px;
    }
    input, button, textarea {
      font: inherit;
      border-radius: 10px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      color: var(--ink);
      background: #fff;
    }
    button {
      cursor: pointer;
      transition: transform .12s ease, background .2s ease;
    }
    button:hover { transform: translateY(-1px); }
    button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    button.alt { background: var(--accent-2); color: #fff; border-color: var(--accent-2); }
    #chat {
      min-height: 0;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 16px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .msg {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: white;
      animation: enter .2s ease;
    }
    .who { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .user { border-left: 4px solid var(--accent); }
    .assistant { border-left: 4px solid #4b6fa3; }
    .bar {
      padding: 14px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr auto auto;
    }
    textarea {
      resize: none;
      min-height: 54px;
      max-height: 54px;
    }
    #status { color: var(--muted); font-size: 13px; }
    @keyframes enter {
      from { opacity: 0; transform: translateY(5px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (max-width: 860px) {
      .top { grid-template-columns: 1fr 1fr; }
      .bar { grid-template-columns: 1fr; }
    }

    @media (max-width: 560px) {
      .top,
      .bar {
        padding: 10px;
      }
      #chat {
        padding: 10px;
      }
    }
  </style>
</head>
<body>
  <main class=\"app\">
    <section class=\"top\">
      <input id=\"prefix\" type=\"text\" placeholder=\"Your name prefix (example: Master)\" />
      <button id=\"voice\" class=\"alt\">Start Voice</button>
      <button id=\"speak\">Bot Voice: OFF</button>
      <button id=\"reset\">Reset Chat</button>
    </section>
    <section id=\"chat\"></section>
    <section class=\"bar\">
      <textarea id=\"msg\" placeholder=\"Type your message...\"></textarea>
      <button id=\"send\" class=\"primary\">Send</button>
      <div id=\"status\">Ready</div>
    </section>
  </main>

  <script>
    const chat = document.getElementById('chat');
    const msg = document.getElementById('msg');
    const statusNode = document.getElementById('status');
    const prefixNode = document.getElementById('prefix');
    const sendBtn = document.getElementById('send');
    const speakBtn = document.getElementById('speak');
    const voiceBtn = document.getElementById('voice');
    const resetBtn = document.getElementById('reset');

    const sessionIdKey = 'gvc-web-session-id';
    const prefixKey = 'gvc-web-prefix';
    const botVoiceKey = 'gvc-web-bot-voice';

    function parseStoredBool(raw) {
      return raw === '1' || raw === 'true' || raw === 'on' || raw === 'yes';
    }

    const sessionId = 'shared';

    let botVoiceEnabled = parseStoredBool(localStorage.getItem(botVoiceKey));
    let listening = false;
    let voiceLoopEnabled = false;
    let wsPort = null;
    let wsBaseUrl = '';
    let botAudioSocket = null;
    let botSfxSocket = null;
    let chatSocket = null;
    let audioContext = null;
    let streamSampleRate = 24000;
    let sfxSampleRate = 24000;
    let audioConnectionToken = 0;
    let sfxConnectionToken = 0;
    let audioUnlockBound = false;
    const audioQueue = [];
    let nextAudioPlayTime = 0;
    let audioPumpScheduled = false;
    let voiceSocket = null;
    let voiceInputContext = null;
    let voiceInputStream = null;
    let voiceSourceNode = null;
    let voiceProcessorNode = null;
    let voiceUtteranceOpen = false;
    let voiceLastSpeechMs = 0;
    const voicePreRollChunks = [];
    const voicePreRollMax = 6;
    let voiceVadNoiseFloor = 0.003;
    let voiceSpeechFrames = 0;
    let voiceSilenceFrames = 0;
    const voiceVadStartFrames = 2;
    const voiceVadEndFrames = 5;
    const voiceVadMinThreshold = 0.01;
    const voiceVadNoiseMultiplier = 3.2;
    let chatConnectionToken = 0;
    let chatRequestCounter = 0;
    const chatPending = new Map();

    function getWsCandidates(path) {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const candidates = [];

      const configuredBase = String(wsBaseUrl || '').trim().replace(/\/$/, '');
      if (configuredBase) {
        candidates.push(configuredBase + path);
      }

      // Prefer same-origin websocket endpoints so reverse proxies (like Cloudflare)
      // can route WS traffic over the same public host/port.
      candidates.push(protocol + '//' + location.host + path);

      if (wsPort) {
        const legacy = protocol + '//' + location.hostname + ':' + wsPort + path;
        if (!candidates.includes(legacy)) {
          candidates.push(legacy);
        }
      }

      return candidates;
    }

    function setStatus(text) {
      statusNode.textContent = text;
    }

    function addMessage(who, text, role) {
      const card = document.createElement('article');
      card.className = 'msg ' + role;

      const whoNode = document.createElement('div');
      whoNode.className = 'who';
      whoNode.textContent = who;

      const textNode = document.createElement('div');
      textNode.textContent = text;

      card.appendChild(whoNode);
      card.appendChild(textNode);
      chat.appendChild(card);
      chat.scrollTop = chat.scrollHeight;
    }

    function handleRealtimePayload(payload) {
      if (payload.type === 'chat_user') {
        const who = payload.prefix || 'Guest';
        const text = payload.text || '';
        if (text) {
          addMessage(who, text, 'user');
        }
        return false;
      }

      if (payload.type === 'voice_transcript') {
        const who = payload.prefix || 'Guest';
        const text = payload.text || '';
        if (text) {
          addMessage(who, text, 'user');
        }
        return false;
      }

      if (payload.type === 'chat_followup' && payload.ok) {
        addMessage('Assistant', payload.reply || '', 'assistant');
        return false;
      }

      if (payload.type === 'chat_status') {
        addMessage('System', payload.message || 'Executing...', 'assistant');
        return false;
      }

      if (payload.type === 'reset_notice') {
        chat.innerHTML = '';
        addMessage('System', payload.message || 'Conversation reset by another user.', 'assistant');
        return false;
      }

      return true;
    }

    async function loadConfig() {
      const res = await fetch('/api/config');
      const data = await res.json();
      const savedPrefix = localStorage.getItem(prefixKey);
      prefixNode.value = savedPrefix || data.default_prefix || 'Guest';
      wsPort = Number(data.ws_port || 8790);
      wsBaseUrl = String(data.ws_base_url || '').trim();
      addMessage('System', 'Connected to ' + (data.ai_name || 'assistant') + '. Prefix can be changed above.', 'assistant');
      connectChatSocket();
      if (botVoiceEnabled) {
        connectBotAudioStream();
        connectBotSfxStream();
      }
    }

    function updateSpeakButton() {
      speakBtn.textContent = 'Bot Voice: ' + (botVoiceEnabled ? 'ON' : 'OFF');
    }

    async function ensureAudioContext(sampleRate) {
      const ContextClass = window.AudioContext || window.webkitAudioContext;
      if (!ContextClass) {
        return false;
      }

      if (!audioContext) {
        audioContext = new ContextClass({ latencyHint: 'interactive', ...(sampleRate ? { sampleRate } : {}) });
      }

      if (audioContext.state !== 'running') {
        try {
          await audioContext.resume();
        } catch (err) {
          return false;
        }
      }
      return audioContext.state === 'running';
    }

    function scheduleAudioPump(delayMs = 0) {
      if (audioPumpScheduled) {
        return;
      }
      audioPumpScheduled = true;
      setTimeout(() => {
        audioPumpScheduled = false;
        pumpAudioQueue();
      }, delayMs);
    }

    async function pumpAudioQueue() {
      const ready = await ensureAudioContext(streamSampleRate);
      if (!ready || !audioContext) {
        setStatus('Bot voice is ON. Tap anywhere to enable audio playback.');
        return;
      }

      if (!audioQueue.length) {
        return;
      }

      const now = audioContext.currentTime;
      if (nextAudioPlayTime < now) {
        nextAudioPlayTime = now;
      }

      while (audioQueue.length) {
        const floatChunk = audioQueue.shift();
        if (!floatChunk || !floatChunk.length) {
          continue;
        }

        const buffer = audioContext.createBuffer(1, floatChunk.length, streamSampleRate);
        buffer.copyToChannel(floatChunk, 0, 0);

        const source = audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(audioContext.destination);
        source.start(nextAudioPlayTime);

        nextAudioPlayTime += floatChunk.length / streamSampleRate;
      }
    }

    function enqueuePcmChunk(arrayBuffer) {
      if (!arrayBuffer) {
        return;
      }
      const floatChunk = new Float32Array(arrayBuffer);
      if (!floatChunk.length) {
        return;
      }
      audioQueue.push(floatChunk);
      scheduleAudioPump(0);
    }

    function bindAudioUnlockHandlers() {
      if (audioUnlockBound) {
        return;
      }
      audioUnlockBound = true;

      const unlock = async () => {
        if (!botVoiceEnabled) {
          return;
        }
        const ready = await ensureAudioContext(streamSampleRate);
        if (ready) {
          setStatus('Bot audio stream connected');
          pumpAudioQueue();
        }
      };

      const options = { passive: true };
      document.addEventListener('pointerdown', unlock, options);
      document.addEventListener('touchstart', unlock, options);
      document.addEventListener('keydown', unlock);
    }

    function closeBotAudioStream() {
      audioConnectionToken += 1;
      sfxConnectionToken += 1;
      if (botAudioSocket) {
        botAudioSocket.close();
        botAudioSocket = null;
      }
      if (botSfxSocket) {
        botSfxSocket.close();
        botSfxSocket = null;
      }
      audioQueue.length = 0;
      nextAudioPlayTime = 0;
    }

    async function connectBotAudioStream() {
      if (!botVoiceEnabled || botAudioSocket) {
        return;
      }

      const candidates = getWsCandidates('/audio');
      let attemptIndex = 0;
      bindAudioUnlockHandlers();
      await ensureAudioContext(streamSampleRate);
      const myToken = ++audioConnectionToken;

      const tryConnect = () => {
        if (myToken !== audioConnectionToken || botAudioSocket) {
          return;
        }
        if (attemptIndex >= candidates.length) {
          setStatus('Bot audio stream unavailable');
          if (botVoiceEnabled) {
            setTimeout(() => {
              if (myToken === audioConnectionToken) {
                connectBotAudioStream();
              }
            }, 1200);
          }
          return;
        }

        const wsUrl = candidates[attemptIndex++];
        const socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';
        let opened = false;

        socket.onopen = () => {
          if (myToken !== audioConnectionToken) {
            try {
              socket.close();
            } catch (err) {
              // ignore
            }
            return;
          }
          opened = true;
          botAudioSocket = socket;
          const outputLatencyMs = audioContext ? Math.round((audioContext.outputLatency || audioContext.baseLatency || 0) * 1000) : 0;
          setStatus('Bot audio stream connected (device output latency: ' + outputLatencyMs + 'ms)');
        };

        socket.onmessage = async (event) => {
          if (myToken !== audioConnectionToken || botAudioSocket !== socket) {
            return;
          }
          if (typeof event.data === 'string') {
            try {
              const meta = JSON.parse(event.data);
              if (meta.type === 'format') {
                streamSampleRate = Number(meta.sample_rate || 24000);
                nextAudioPlayTime = 0;
                await ensureAudioContext(streamSampleRate);
                pumpAudioQueue();
              }
            } catch (err) {
              console.warn('Audio metadata parse failed', err);
            }
            return;
          }

          if (botVoiceEnabled) {
            enqueuePcmChunk(event.data);
          }
        };

        socket.onerror = () => {
          if (myToken !== audioConnectionToken) {
            return;
          }
          if (opened && botAudioSocket === socket) {
            setStatus('Bot audio stream error');
          }
        };

        socket.onclose = () => {
          if (myToken !== audioConnectionToken) {
            return;
          }
          if (!opened) {
            tryConnect();
            return;
          }

          if (botAudioSocket === socket) {
            botAudioSocket = null;
            if (botVoiceEnabled) {
              setTimeout(() => {
                connectBotAudioStream();
              }, 1200);
            }
          }
        };
      };

      tryConnect();
    }

    async function connectBotSfxStream() {
      if (!botVoiceEnabled || botSfxSocket) {
        return;
      }

      const candidates = getWsCandidates('/sfx');
      let attemptIndex = 0;
      bindAudioUnlockHandlers();
      await ensureAudioContext(sfxSampleRate);
      const myToken = ++sfxConnectionToken;

      const tryConnect = () => {
        if (myToken !== sfxConnectionToken || botSfxSocket) {
          return;
        }
        if (attemptIndex >= candidates.length) {
          if (botVoiceEnabled) {
            setTimeout(() => {
              if (myToken === sfxConnectionToken) {
                connectBotSfxStream();
              }
            }, 1200);
          }
          return;
        }

        const wsUrl = candidates[attemptIndex++];
        const socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';
        let opened = false;

        socket.onopen = () => {
          if (myToken !== sfxConnectionToken) {
            try {
              socket.close();
            } catch (err) {
              // ignore
            }
            return;
          }
          opened = true;
          botSfxSocket = socket;
        };

        socket.onmessage = async (event) => {
          if (myToken !== sfxConnectionToken || botSfxSocket !== socket) {
            return;
          }
          if (typeof event.data === 'string') {
            try {
              const meta = JSON.parse(event.data);
              if (meta.type === 'format') {
                sfxSampleRate = Number(meta.sample_rate || 24000);
                await ensureAudioContext(sfxSampleRate);
              }
            } catch (err) {
              console.warn('SFX metadata parse failed', err);
            }
            return;
          }

          if (!botVoiceEnabled) {
            return;
          }

          const ready = await ensureAudioContext(sfxSampleRate);
          if (!ready || !audioContext) {
            return;
          }

          const floatChunk = new Float32Array(event.data);
          if (!floatChunk.length) {
            return;
          }

          const buffer = audioContext.createBuffer(1, floatChunk.length, sfxSampleRate);
          buffer.copyToChannel(floatChunk, 0, 0);
          const source = audioContext.createBufferSource();
          source.buffer = buffer;
          source.connect(audioContext.destination);
          source.start();
        };

        socket.onclose = () => {
          if (myToken !== sfxConnectionToken) {
            return;
          }
          if (!opened) {
            tryConnect();
            return;
          }
          if (botSfxSocket === socket) {
            botSfxSocket = null;
            if (botVoiceEnabled) {
              setTimeout(() => {
                connectBotSfxStream();
              }, 1200);
            }
          }
        };
      };

      tryConnect();
    }

    function connectChatSocket() {
      if (chatSocket) {
        return;
      }
      const myToken = ++chatConnectionToken;

      const candidates = getWsCandidates('/chat');
      let attemptIndex = 0;

      const tryConnect = () => {
        if (myToken !== chatConnectionToken || chatSocket) {
          return;
        }
        if (attemptIndex >= candidates.length) {
          setStatus('Realtime chat socket unavailable');
          setTimeout(() => {
            if (myToken === chatConnectionToken) {
              connectChatSocket();
            }
          }, 1200);
          return;
        }

        const wsUrl = candidates[attemptIndex++];
        const socket = new WebSocket(wsUrl);
        let opened = false;

        socket.onopen = () => {
          if (myToken !== chatConnectionToken) {
            try {
              socket.close();
            } catch (err) {
              // ignore
            }
            return;
          }
          opened = true;
          chatSocket = socket;
          setStatus('Realtime chat connected');
        };

        socket.onmessage = (event) => {
          if (myToken !== chatConnectionToken || chatSocket !== socket || typeof event.data !== 'string') {
            return;
          }
          let payload = null;
          try {
            payload = JSON.parse(event.data);
          } catch (err) {
            return;
          }

          if (!handleRealtimePayload(payload)) {
            return;
          }

          const requestId = payload.request_id;
          if (requestId && chatPending.has(requestId)) {
            const pending = chatPending.get(requestId);
            chatPending.delete(requestId);
            pending.resolve(payload);
          }
        };

        socket.onerror = () => {
          if (myToken !== chatConnectionToken) {
            return;
          }
          if (opened && chatSocket === socket) {
            setStatus('Realtime chat socket error');
          }
        };

        socket.onclose = () => {
          if (myToken !== chatConnectionToken) {
            return;
          }

          if (!opened) {
            tryConnect();
            return;
          }

          if (chatSocket === socket) {
            chatSocket = null;
            const pendings = Array.from(chatPending.values());
            chatPending.clear();
            for (const item of pendings) {
              item.reject(new Error('Realtime chat disconnected'));
            }
            setTimeout(() => {
              connectChatSocket();
            }, 1000);
          }
        };
      };

      tryConnect();
    }

    function waitForChatSocket(timeoutMs) {
      return new Promise((resolve, reject) => {
        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
          resolve();
          return;
        }

        connectChatSocket();

        const pollId = setInterval(() => {
          if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            clearInterval(pollId);
            clearTimeout(timeoutId);
            resolve();
          }
        }, 100);

        const timeoutId = setTimeout(() => {
          clearInterval(pollId);
          reject(new Error('Realtime chat is not connected'));
        }, timeoutMs || 6000);
      });
    }

    function floatToInt16Buffer(floatArray) {
      const buffer = new ArrayBuffer(floatArray.length * 2);
      const view = new DataView(buffer);
      for (let i = 0; i < floatArray.length; i++) {
        let s = Math.max(-1, Math.min(1, floatArray[i]));
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
      return buffer;
    }

    function closeVoiceSocket() {
      if (voiceSocket) {
        try {
          voiceSocket.close();
        } catch (err) {
          // ignore
        }
      }
      voiceSocket = null;
    }

    async function connectVoiceSocket() {
      if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN) {
        return;
      }

      const candidates = getWsCandidates('/voice');
      let lastError = null;

      for (const wsUrl of candidates) {
        const socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';

        try {
          await new Promise((resolve, reject) => {
            const onOpen = () => {
              socket.removeEventListener('open', onOpen);
              socket.removeEventListener('error', onErr);
              resolve();
            };
            const onErr = () => {
              socket.removeEventListener('open', onOpen);
              socket.removeEventListener('error', onErr);
              reject(new Error('Voice websocket connection failed'));
            };
            socket.addEventListener('open', onOpen);
            socket.addEventListener('error', onErr);
          });

          voiceSocket = socket;
          voiceSocket.onmessage = (event) => {
            if (voiceSocket !== socket || typeof event.data !== 'string') {
              return;
            }
            let payload = null;
            try {
              payload = JSON.parse(event.data);
            } catch (err) {
              return;
            }

            if (!handleRealtimePayload(payload)) {
              return;
            }

            if (payload.type === 'chat_reply') {
              if (payload.ok) {
                addMessage('Assistant', payload.reply || '', 'assistant');
                setStatus('Ready');
              } else {
                addMessage('System', 'Error: ' + (payload.error || 'Request failed'), 'assistant');
                setStatus('Error');
              }
              return;
            }

            if (payload.type === 'error') {
              const msg = payload.error || 'Voice websocket error';
              addMessage('System', 'Error: ' + msg, 'assistant');
              setStatus('Error');
            }
          };

          voiceSocket.onclose = () => {
            if (voiceSocket === socket) {
              voiceSocket = null;
            }
          };

          return;
        } catch (err) {
          lastError = err;
          try {
            socket.close();
          } catch (closeErr) {
            // ignore
          }
        }
      }

      throw lastError || new Error('Voice websocket connection failed');
    }

    function teardownVoiceCapture() {
      if (voiceProcessorNode) {
        try {
          voiceProcessorNode.disconnect();
        } catch (err) {
          // ignore
        }
      }
      if (voiceSourceNode) {
        try {
          voiceSourceNode.disconnect();
        } catch (err) {
          // ignore
        }
      }
      voiceProcessorNode = null;
      voiceSourceNode = null;

      if (voiceInputStream) {
        for (const track of voiceInputStream.getTracks()) {
          track.stop();
        }
      }
      voiceInputStream = null;
      voicePreRollChunks.length = 0;
      voiceUtteranceOpen = false;
      voiceSpeechFrames = 0;
      voiceSilenceFrames = 0;
    }

    async function startVoiceCapture() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Browser microphone capture is not supported');
      }

      await connectVoiceSocket();
      voiceInputStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      if (!voiceInputContext) {
        const ContextClass = window.AudioContext || window.webkitAudioContext;
        voiceInputContext = new ContextClass();
      }
      if (voiceInputContext.state === 'suspended') {
        await voiceInputContext.resume();
      }

      voiceSourceNode = voiceInputContext.createMediaStreamSource(voiceInputStream);
      voiceProcessorNode = voiceInputContext.createScriptProcessor(4096, 1, 1);
      voiceSourceNode.connect(voiceProcessorNode);
      // Keep processor alive across browsers without audible output.
      voiceProcessorNode.connect(voiceInputContext.destination);

      voiceProcessorNode.onaudioprocess = (event) => {
        if (!voiceLoopEnabled || !voiceSocket || voiceSocket.readyState !== WebSocket.OPEN) {
          return;
        }

        const input = event.inputBuffer.getChannelData(0);
        const chunkBuffer = floatToInt16Buffer(input);

        let sumSq = 0;
        for (let i = 0; i < input.length; i++) {
          sumSq += input[i] * input[i];
        }
        const rms = Math.sqrt(sumSq / Math.max(1, input.length));
        if (!voiceUtteranceOpen) {
          // Track ambient floor only outside active utterance.
          voiceVadNoiseFloor = (voiceVadNoiseFloor * 0.98) + (rms * 0.02);
        }
        const dynamicThreshold = Math.max(voiceVadMinThreshold, voiceVadNoiseFloor * voiceVadNoiseMultiplier);
        const isSpeech = rms >= dynamicThreshold;

        if (!voiceUtteranceOpen) {
          voicePreRollChunks.push(chunkBuffer);
          if (voicePreRollChunks.length > voicePreRollMax) {
            voicePreRollChunks.shift();
          }

          if (isSpeech) {
            voiceSpeechFrames += 1;
          } else {
            voiceSpeechFrames = 0;
          }
        }

        if (!voiceUtteranceOpen) {
          if (voiceSpeechFrames >= voiceVadStartFrames) {
            const prefix = prefixNode.value.trim() || 'Guest';
            localStorage.setItem(prefixKey, prefix);
            voiceSocket.send(JSON.stringify({
              type: 'voice_start',
              session_id: sessionId,
              prefix,
              sample_rate: Math.round(voiceInputContext.sampleRate),
              speak_bot_voice: botVoiceEnabled,
            }));
            for (const preChunk of voicePreRollChunks) {
              voiceSocket.send(preChunk);
            }
            voicePreRollChunks.length = 0;
            voiceUtteranceOpen = true;
            voiceSilenceFrames = 0;
            voiceSpeechFrames = 0;
            voiceLastSpeechMs = performance.now();
            return;
          }
          return;
        }

        if (isSpeech) {
          voiceLastSpeechMs = performance.now();
          voiceSilenceFrames = 0;
          voiceSocket.send(chunkBuffer);
          return;
        }

        voiceSilenceFrames += 1;
        if (voiceSilenceFrames >= voiceVadEndFrames) {
          voiceSocket.send(JSON.stringify({ type: 'voice_end' }));
          voiceUtteranceOpen = false;
          voicePreRollChunks.length = 0;
          voiceSilenceFrames = 0;
          voiceSpeechFrames = 0;
        }
      };
    }

    async function sendChatWs(payload, timeoutMs) {
      await waitForChatSocket(1500);

      return new Promise((resolve, reject) => {
        if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
          reject(new Error('Realtime chat is not connected'));
          return;
        }

        const requestId = String(++chatRequestCounter) + '-' + Date.now();
        const timer = setTimeout(() => {
          chatPending.delete(requestId);
          reject(new Error('Realtime request timeout'));
        }, timeoutMs || 180000);

        chatPending.set(requestId, {
          resolve: (data) => {
            clearTimeout(timer);
            resolve(data);
          },
          reject: (err) => {
            clearTimeout(timer);
            reject(err);
          },
        });

        chatSocket.send(JSON.stringify({ ...payload, request_id: requestId }));
      });
    }

    async function sendChatHttp(payload) {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: payload.session_id,
          prefix: payload.prefix,
          message: payload.message,
          speak_bot_voice: payload.speak_bot_voice,
        }),
      });
      const data = await res.json();
      if (!res.ok && !data.ok) {
        throw new Error(data.error || 'HTTP chat request failed');
      }
      return {
        ok: true,
        reply: data.reply || '',
      };
    }

    async function sendResetHttp(sessionIdValue) {
      const res = await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionIdValue }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'HTTP reset request failed');
      }
      return data;
    }

    function startListening() {
      if (listening) {
        return;
      }
      voiceLoopEnabled = true;
      startVoiceCapture().then(() => {
        listening = true;
        voiceBtn.textContent = 'Stop Voice';
        setStatus('Listening (PC pipeline)...');
      }).catch((err) => {
        voiceLoopEnabled = false;
        listening = false;
        voiceBtn.textContent = 'Start Voice';
        setStatus('Voice start failed: ' + err.message);
        teardownVoiceCapture();
        closeVoiceSocket();
      });
    }

    function stopListening() {
      voiceLoopEnabled = false;
      if (voiceSocket && voiceSocket.readyState === WebSocket.OPEN && voiceUtteranceOpen) {
        voiceSocket.send(JSON.stringify({ type: 'voice_end' }));
      }
      teardownVoiceCapture();
      closeVoiceSocket();
      listening = false;
      voiceBtn.textContent = 'Start Voice';
      setStatus('Voice stopped');
    }

    async function sendMessage() {
      const text = msg.value.trim();
      if (!text) {
        return;
      }
      const prefix = prefixNode.value.trim() || 'Guest';
      localStorage.setItem(prefixKey, prefix);
      addMessage(prefix, text, 'user');
      msg.value = '';
      setStatus('Sending...');
      sendBtn.disabled = true;

      try {
        connectChatSocket();
        const payload = {
          type: 'chat',
          session_id: sessionId,
          prefix,
          message: text,
          speak_bot_voice: botVoiceEnabled
        };

        let data = null;
        try {
          data = await sendChatWs(payload, 180000);
        } catch (err) {
          // Fallback to HTTP when websocket endpoint is unavailable behind proxies.
          data = await sendChatHttp(payload);
        }

        if (!data.ok) {
          throw new Error(data.error || 'Request failed');
        }
        addMessage('Assistant', data.reply, 'assistant');
        setStatus('Ready');
      } catch (err) {
        addMessage('System', 'Error: ' + err.message, 'assistant');
        setStatus('Error');
      } finally {
        sendBtn.disabled = false;
      }
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      voiceBtn.disabled = true;
      voiceBtn.textContent = 'Voice Unsupported';
    }

    sendBtn.addEventListener('click', () => sendMessage());
    msg.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    prefixNode.addEventListener('change', () => {
      localStorage.setItem(prefixKey, prefixNode.value.trim() || 'Guest');
    });

    speakBtn.addEventListener('click', () => {
      botVoiceEnabled = !botVoiceEnabled;
      localStorage.setItem(botVoiceKey, botVoiceEnabled ? '1' : '0');
      updateSpeakButton();
      if (botVoiceEnabled) {
        connectBotAudioStream();
        connectBotSfxStream();
      } else {
        closeBotAudioStream();
      }
    });

    voiceBtn.addEventListener('click', () => {
      if (!voiceLoopEnabled) {
        startListening();
      } else {
        stopListening();
      }
    });

    resetBtn.addEventListener('click', async () => {
      try {
        connectChatSocket();
        let data = null;
        try {
          data = await sendChatWs({ type: 'reset', session_id: sessionId }, 30000);
        } catch (err) {
          data = await sendResetHttp(sessionId);
        }
        if (!data.ok) {
          throw new Error(data.error || 'Reset failed');
        }
        chat.innerHTML = '';
        addMessage('System', 'Conversation reset.', 'assistant');
      } catch (err) {
        addMessage('System', 'Reset failed: ' + err.message, 'assistant');
      }
    });

    updateSpeakButton();
    loadConfig().catch((err) => {
      addMessage('System', 'Failed to load config: ' + err.message, 'assistant');
    });
  </script>
</body>
</html>
"""


def detect_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def build_handler(service: WebChatService):
  ws_proxy_paths = {"/chat", "/voice", "/audio", "/sfx"}

  class Handler(BaseHTTPRequestHandler):
    def _is_websocket_upgrade(self):
      connection_value = str(self.headers.get("Connection") or "").lower()
      upgrade_value = str(self.headers.get("Upgrade") or "").lower()
      return "upgrade" in connection_value and upgrade_value == "websocket"

    def _open_ws_upstream(self):
      upstream = socket.create_connection((service.ws_upstream_host, service.ws_upstream_port), timeout=10)
      try:
        upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
      except OSError:
        pass
      if service.ws_upstream_tls:
        context = ssl.create_default_context()
        if not service.ws_upstream_tls_verify:
          context.check_hostname = False
          context.verify_mode = ssl.CERT_NONE
        server_name = service.ws_upstream_server_name or service.ws_upstream_host
        upstream = context.wrap_socket(upstream, server_hostname=server_name)
      return upstream

    @staticmethod
    def _pipe_socket(src, dst):
      try:
        while True:
          chunk = src.recv(16384)
          if not chunk:
            break
          dst.sendall(chunk)
      except OSError:
        pass
      finally:
        try:
          dst.shutdown(socket.SHUT_WR)
        except OSError:
          pass

    def _proxy_websocket(self):
      try:
        upstream = self._open_ws_upstream()
      except Exception as e:
        self._send_json({"error": f"Websocket upstream unavailable: {e}"}, status=HTTPStatus.BAD_GATEWAY)
        return

      try:
        request_lines = [f"GET {self.path} HTTP/1.1"]
        request_lines.append(f"Host: {service.ws_upstream_host}:{service.ws_upstream_port}")
        for key, value in self.headers.items():
          if key.lower() == "host":
            continue
          request_lines.append(f"{key}: {value}")
        raw_request = ("\r\n".join(request_lines) + "\r\n\r\n").encode("utf-8")
        upstream.sendall(raw_request)

        response_bytes = b""
        while b"\r\n\r\n" not in response_bytes and len(response_bytes) < 131072:
          part = upstream.recv(4096)
          if not part:
            break
          response_bytes += part

        if not response_bytes:
          self._send_json({"error": "Empty websocket upstream response"}, status=HTTPStatus.BAD_GATEWAY)
          return

        self.connection.sendall(response_bytes)

        status_line = response_bytes.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
        if " 101 " not in status_line:
          return

        try:
          self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
          pass

        self.connection.settimeout(None)
        upstream.settimeout(None)
        client_to_upstream = threading.Thread(
          target=self._pipe_socket,
          args=(self.connection, upstream),
          daemon=True,
        )
        upstream_to_client = threading.Thread(
          target=self._pipe_socket,
          args=(upstream, self.connection),
          daemon=True,
        )
        client_to_upstream.start()
        upstream_to_client.start()
        client_to_upstream.join()
        upstream_to_client.join()
      finally:
        try:
          upstream.close()
        except OSError:
          pass

    def _send_json(self, data, status=HTTPStatus.OK):
      payload = json.dumps(data).encode("utf-8")
      self.send_response(status)
      self.send_header("Content-Type", "application/json; charset=utf-8")
      self.send_header("Content-Length", str(len(payload)))
      self.end_headers()
      self.wfile.write(payload)

    def _send_html(self, text, status=HTTPStatus.OK):
      payload = text.encode("utf-8")
      self.send_response(status)
      self.send_header("Content-Type", "text/html; charset=utf-8")
      self.send_header("Content-Length", str(len(payload)))
      self.end_headers()
      self.wfile.write(payload)

    def _read_json(self):
      length = int(self.headers.get("Content-Length", "0"))
      raw = self.rfile.read(length) if length > 0 else b"{}"
      return json.loads(raw.decode("utf-8"))

    def do_GET(self):
      if self.path in ws_proxy_paths and self._is_websocket_upgrade():
        self._proxy_websocket()
        return

      if self.path == "/":
        self._send_html(HTML_PAGE)
        return
      if self.path == "/api/config":
        self._send_json(
          {
            "ai_name": service.ai_name,
            "default_prefix": service.default_prefix,
            "ws_port": service.ws_port,
            "ws_base_url": str(service.config.get("web_ws_base_url") or "").strip(),
          }
        )
        return
      if self.path == "/health":
        self._send_json({"status": "ok"})
        return
      self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
      try:
        data = self._read_json()
      except Exception:
        self._send_json({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
        return

      if self.path == "/api/chat":
        session_id = str(data.get("session_id") or "default")
        message = str(data.get("message") or "").strip()
        prefix = str(data.get("prefix") or service.default_prefix)
        speak_bot_voice = bool(data.get("speak_bot_voice", False))

        if not message:
          self._send_json({"error": "message is required"}, status=HTTPStatus.BAD_REQUEST)
          return

        try:
          result = service.chat(
            session_id=session_id,
            prefix=prefix,
            message=message,
            speak_bot_voice=speak_bot_voice,
          )
          self._send_json(result)
        except Exception as e:
          self._send_json({"error": str(e)}, status=HTTPStatus.BAD_GATEWAY)
        return

      if self.path == "/api/reset":
        session_id = str(data.get("session_id") or "default")
        try:
          service.reset(session_id)
          self._send_json({"status": "ok"})
        except Exception as e:
          self._send_json({"error": str(e)}, status=HTTPStatus.BAD_GATEWAY)
        return

      self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt, *args):
      print("[web]", fmt % args)

  return Handler


def run_server(
    host: str,
    port: int,
    config_path: str,
    default_prefix: str | None,
    ipc_host: str | None,
    ipc_port: int | None,
    ipc_auth: str | None,
  ws_port: int | None,
  tls_enabled: bool | None,
  tls_certfile: str | None,
  tls_keyfile: str | None,
):
    config = load_config(config_path)
    service = WebChatService(
        config=config,
        default_prefix=default_prefix,
        ipc_host=ipc_host,
        ipc_port=ipc_port,
        ipc_auth=ipc_auth,
        ws_port=ws_port,
    )
    handler = build_handler(service)
    server = ThreadingHTTPServer((host, port), handler)

    effective_tls_enabled = parse_bool(tls_enabled) if tls_enabled is not None else parse_bool(config.get("web_tls_enabled"))
    effective_certfile = str(tls_certfile if tls_certfile is not None else config.get("web_tls_certfile") or "").strip()
    effective_keyfile = str(tls_keyfile if tls_keyfile is not None else config.get("web_tls_keyfile") or "").strip()

    if effective_tls_enabled:
      if not effective_certfile or not effective_keyfile:
        raise RuntimeError("HTTPS enabled but web_tls_certfile/web_tls_keyfile are not configured")
      cert_path = Path(effective_certfile)
      key_path = Path(effective_keyfile)
      if not cert_path.exists() or not key_path.exists():
        raise RuntimeError("HTTPS cert/key file not found")

      context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
      context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
      server.socket = context.wrap_socket(server.socket, server_side=True)

    lan_ip = detect_lan_ip()
    scheme = "https" if effective_tls_enabled else "http"
    print(f"Web chat server running on {scheme}://{host}:{port}")
    if host in ("0.0.0.0", ""):
      print(f"LAN access URL: {scheme}://{lan_ip}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down web chat server...")
    finally:
        server.server_close()


def parse_args():
    parser = argparse.ArgumentParser(description="Gemini Voice Companion web chat server")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--default-prefix", default=None, help="Default speaker prefix")
    parser.add_argument("--ipc-host", default=None, help="IPC backend host")
    parser.add_argument("--ipc-port", type=int, default=None, help="IPC backend port")
    parser.add_argument("--ipc-auth", default=None, help="IPC backend auth key")
    parser.add_argument("--ws-port", type=int, default=None, help="Backend audio websocket port")
    parser.add_argument("--tls-enabled", default=None, help="Enable HTTPS: true/false")
    parser.add_argument("--tls-cert", default=None, help="HTTPS TLS cert file path")
    parser.add_argument("--tls-key", default=None, help="HTTPS TLS key file path")
    return parser.parse_args()


def main():
    args = parse_args()
    run_server(
        host=args.host,
        port=args.port,
        config_path=args.config,
        default_prefix=args.default_prefix,
        ipc_host=args.ipc_host,
        ipc_port=args.ipc_port,
        ipc_auth=args.ipc_auth,
        ws_port=args.ws_port,
        tls_enabled=args.tls_enabled,
        tls_certfile=args.tls_cert,
        tls_keyfile=args.tls_key,
    )


if __name__ == "__main__":
    main()
