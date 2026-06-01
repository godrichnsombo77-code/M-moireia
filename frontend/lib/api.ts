// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Alert {
  id: number;
  timestamp: string;
  niveau: string;
  priorite: number;
  message: string;
  classes_detectees: string[];
  photo_path?: string;
  video_path?: string;
  resolved?: boolean;
}

export interface Stats {
  total_alerts: number;
  unread: number;
  active_cameras: number;
  evidences: number;
}

export interface AnalysisResult {
  alert: {
    niveau: string;
    priorite: number;
    message: string;
    classes_detectees: string[];
  };
  detections: Array<{ class_id: number; score: number }>;
  evidence_photo?: string;
  preview_image?: string;
  qwen_summary?: string;
  qwen_escalated: boolean;
  audio_url?: string;
}

export interface ChatResponse {
  message: string;
  answer: string;
  model: string;
  visual_context_used: boolean;
  audio_url?: string;
}

// Fetch helpers
export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE_URL}/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchRecentAlerts(limit = 10): Promise<{ alerts: Alert[] }> {
  const res = await fetch(`${API_BASE_URL}/alerts/recent?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch alerts");
  return res.json();
}

export async function analyzeFrame(
  file: File | Blob,
  options: {
    threshold?: number;
    saveEvidence?: boolean;
    runQwen?: boolean;
    responseMode?: "text" | "voice";
  } = {}
): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("threshold", String(options.threshold ?? 0.1));
  form.append("save_evidence", String(options.saveEvidence ?? true));
  form.append("run_qwen", String(options.runQwen ?? true));
  form.append("response_mode", options.responseMode ?? "text");

  const res = await fetch(`${API_BASE_URL}/analyze/frame`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to analyze frame");
  return res.json();
}

export async function analyzeVideo(
  file: File,
  options: {
    threshold?: number;
    sampleEveryNFrames?: number;
    runQwen?: boolean;
    qwenCleanFrameThreshold?: number;
    responseMode?: "text" | "voice";
  } = {}
): Promise<AnalysisResult & { annotated_video_url?: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("threshold", String(options.threshold ?? 0.1));
  form.append("sample_every_n_frames", String(options.sampleEveryNFrames ?? 15));
  form.append("run_qwen", String(options.runQwen ?? true));
  form.append("qwen_clean_frame_threshold", String(options.qwenCleanFrameThreshold ?? 6));
  form.append("response_mode", options.responseMode ?? "text");

  const res = await fetch(`${API_BASE_URL}/analyze/video`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to analyze video");
  return res.json();
}

export async function analyzeLiveFrame(
  blob: Blob,
  options: {
    threshold?: number;
    sourceMode?: "webcam" | "surveillance";
  } = {}
): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", blob, "webcam.jpg");
  form.append("threshold", String(options.threshold ?? 0.1));
  form.append("save_evidence", "true");
  form.append("run_qwen", "true");
  form.append("response_mode", "text");
  form.append("source_mode", options.sourceMode ?? "webcam");

  const res = await fetch(`${API_BASE_URL}/live/frame`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to analyze live frame");
  return res.json();
}

export async function sendChat(
  message: string,
  options: {
    systemPrompt?: string;
    responseMode?: "text" | "voice";
  } = {}
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("message", message);
  form.append(
    "system_prompt",
    options.systemPrompt ??
      "Tu es un assistant de surveillance. Reponds de maniere courte, claire et operationnelle."
  );
  form.append("response_mode", options.responseMode ?? "text");

  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Failed to send chat");
  return res.json();
}

export async function checkHealth(): Promise<{
  ok: boolean;
  service: string;
  qwen_dashscope_configured: boolean;
  qwen_model: string;
}> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error("API unavailable");
  return res.json();
}

// WebSocket helper
export function createLiveSocket(
  onMessage: (data: unknown) => void,
  onConnect?: () => void,
  onDisconnect?: () => void
): WebSocket {
  const protocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = API_BASE_URL.replace(/^https?:\/\//, "");
  const socket = new WebSocket(`${protocol}//${host}/ws/live`);

  socket.onopen = () => {
    onConnect?.();
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      // Ignore invalid JSON
    }
  };

  socket.onclose = () => {
    onDisconnect?.();
  };

  return socket;
}

// Class ID to label mapping
export const CLASS_LABELS: Record<number, string> = {
  0: "Normal",
  1: "Violence",
  2: "Arme a feu",
  3: "Couteau",
  4: "Personne",
};

export const ALERT_LEVELS: Record<string, { color: string; bgColor: string; label: string }> = {
  INFO: { color: "text-blue-400", bgColor: "bg-blue-400/10", label: "Info" },
  MODERE: { color: "text-emerald-400", bgColor: "bg-emerald-400/10", label: "Modere" },
  ELEVE: { color: "text-amber-400", bgColor: "bg-amber-400/10", label: "Eleve" },
  CRITIQUE: { color: "text-red-400", bgColor: "bg-red-400/10", label: "Critique" },
  URGENCE: { color: "text-red-500", bgColor: "bg-red-500/20", label: "Urgence" },
};
