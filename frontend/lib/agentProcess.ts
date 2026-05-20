import { ChildProcessWithoutNullStreams, spawn } from "child_process";
import { EventEmitter } from "events";
import path from "path";

type AgentState = {
  running: boolean;
  connected: boolean;
  listening: boolean;
  speaking: boolean;
};

type AgentEvent =
  | { type: "state"; data: AgentState }
  | { type: "log"; text: string }
  | { type: "user_transcript"; text: string }
  | { type: "assistant_response"; text: string };

const bus = new EventEmitter();
bus.setMaxListeners(100);

let proc: ChildProcessWithoutNullStreams | null = null;
let stdoutBuffer = "";
let stderrBuffer = "";
let speakingReset: NodeJS.Timeout | null = null;
let lastSpeaker: "you" | "interviewer" | "system" | null = null;

const state: AgentState = {
  running: false,
  connected: false,
  listening: false,
  speaking: false
};

function emit(event: AgentEvent) {
  bus.emit("event", event);
}

function emitState() {
  emit({ type: "state", data: { ...state } });
}

function setSpeaking(value: boolean) {
  state.speaking = value;
  emitState();
}

function parseLine(rawLine: string) {
  const line = rawLine.trim();
  if (!line) return;

  emit({ type: "log", text: line });

  if (line.includes("Deepgram STT connected")) {
    state.connected = true;
    emitState();
    return;
  }

  if (line.includes("Listening from microphone")) {
    state.listening = true;
    emitState();
    return;
  }

  if (line.startsWith("[You]:")) {
    lastSpeaker = "you";
    emit({ type: "user_transcript", text: line.replace("[You]:", "").trim() });
    return;
  }

  if (line.startsWith("[Interviewer]:")) {
    lastSpeaker = "interviewer";
    emit({
      type: "assistant_response",
      text: line.replace("[Interviewer]:", "").trim()
    });
    if (speakingReset) clearTimeout(speakingReset);
    setSpeaking(true);
    speakingReset = setTimeout(() => setSpeaking(false), 4500);
    return;
  }

  if (line.startsWith("[TTS]")) {
    lastSpeaker = "system";
    emit({ type: "log", text: line });
    if (line.includes("Generating") || line.includes("Playing")) {
      if (speakingReset) clearTimeout(speakingReset);
      setSpeaking(true);
      speakingReset = setTimeout(() => setSpeaking(false), 4500);
    }
    return;
  }

  // Keep multi-line interviewer answers visible in the chat feed.
  if (lastSpeaker === "interviewer") {
    emit({ type: "assistant_response", text: line });
    return;
  }

  if (line.includes("Deepgram STT closed") || line.includes("Stopped local mode")) {
    state.connected = false;
    state.listening = false;
    setSpeaking(false);
    emitState();
  }
}

function wireStream(data: string, target: "stdout" | "stderr") {
  let buffer = target === "stdout" ? stdoutBuffer : stderrBuffer;
  buffer += data;
  const lines = buffer.split(/\r?\n/);
  buffer = lines.pop() ?? "";
  for (const line of lines) parseLine(line);
  if (target === "stdout") stdoutBuffer = buffer;
  else stderrBuffer = buffer;
}

export function startAgent() {
  if (proc) {
    return { alreadyRunning: true };
  }

  const projectRoot = path.resolve(process.cwd(), "..");
  const backendRoot = path.resolve(projectRoot, "backend");
  const scriptPath = path.resolve(backendRoot, "main.py");
  const pythonCmd = process.env.PYTHON_CMD || "python";

  proc = spawn(pythonCmd, [scriptPath], {
    cwd: backendRoot,
    env: process.env,
    windowsHide: true
  });

  state.running = true;
  state.connected = false;
  state.listening = false;
  state.speaking = false;
  emitState();

  proc.stdout.on("data", (chunk) => wireStream(String(chunk), "stdout"));
  proc.stderr.on("data", (chunk) => wireStream(String(chunk), "stderr"));

  proc.on("exit", (code) => {
    parseLine(`Agent exited with code ${code ?? "null"}`);
    proc = null;
    state.running = false;
    state.connected = false;
    state.listening = false;
    state.speaking = false;
    emitState();
  });

  proc.on("error", (err) => {
    parseLine(`Agent process error: ${err.message}`);
  });

  return { alreadyRunning: false };
}

export function stopAgent() {
  if (!proc) return { alreadyStopped: true };
  proc.kill();
  return { alreadyStopped: false };
}

export function subscribe(handler: (event: AgentEvent) => void) {
  bus.on("event", handler);
  return () => bus.off("event", handler);
}

export function getAgentState(): AgentState {
  return { ...state };
}
