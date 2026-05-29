import base64
import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import dashscope
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from utils.alerte import get_alerte
from utils.database import get_alerts, get_dashboard_stats, init_db, save_alert
from utils.detection import ModelNotAvailableError, get_detector
from utils.voice import text_to_speech_file, transcribe_audio_file
from utils.video_recorder import save_photo


APP_TITLE = "Surveillance API - YOLO + Qwen"
BASE_DIR = Path(__file__).resolve().parent
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
dashscope.base_http_api_url = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/api/v1",
).strip()
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-vl-plus").strip()
QWEN_CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen-plus").strip()
PROCESSED_DIR = Path("evidences") / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

RECENT_FRAMES: list[np.ndarray] = []
LAST_MEDIA_KIND: str | None = None
LAST_IMAGE_FRAME: np.ndarray | None = None
LAST_ANNOTATED_IMAGE: np.ndarray | None = None
LAST_ANNOTATED_VIDEO: str | None = None
LAST_MEDIA_NOTE: str | None = None
LIVE_CONNECTIONS: set[WebSocket] = set()


def decode_image_bytes(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Image non lisible.")
    return frame


def summarize_detections(class_ids: list[int], scores: list[float]) -> list[dict[str, Any]]:
    items = []
    for class_id, score in zip(class_ids, scores):
        items.append(
            {
                "class_id": int(class_id),
                "score": float(round(score, 4)),
            }
        )
    return items


def should_escalate_to_qwen(class_ids: list[int], alerte: dict) -> bool:
    """
    Decide when YOLO should forward scene to Qwen.
    Rule: escalate only on meaningful risk.
    """
    if not class_ids:
        return False

    # Main gate: only moderate+ with at least one real object.
    if alerte.get("priorite", 0) < 1:
        return False

    cls = set(int(c) for c in class_ids)
    has_person = 4 in cls
    has_weapon = 2 in cls or 3 in cls
    has_violence = 1 in cls

    # Escalate if high risk combo exists.
    if has_weapon or has_violence:
        return True
    if has_person and alerte.get("priorite", 0) >= 2:
        return True
    return False


def to_base64_jpg(frame: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise ValueError("Encodage image impossible.")
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def build_frame_contact_sheet(frames: list[np.ndarray], cols: int = 2, max_frames: int = 4) -> np.ndarray:
    if not frames:
        raise ValueError("Aucune frame a assembler.")

    selected = frames[-max_frames:]
    resized = []
    target_w, target_h = 512, 288
    for frame in selected:
        resized.append(cv2.resize(frame, (target_w, target_h)))

    blank = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    while len(resized) % cols != 0:
        resized.append(blank.copy())

    rows = []
    for i in range(0, len(resized), cols):
        rows.append(np.hstack(resized[i : i + cols]))

    return np.vstack(rows)


def call_qwen_dashscope(
    image_b64: str,
    prompt: str,
    max_tokens: int = 180,
    model: str = QWEN_MODEL,
) -> str:
    if not dashscope.api_key:
        return "DASHSCOPE_API_KEY non configuree."

    messages = [
        {
            "role": "system",
            "content": [{"text": "Tu es un analyste de videosurveillance. Reponds de facon concise et factuelle."}],
        },
        {
            "role": "user",
            "content": [
                {"image": f"data:image/jpeg;base64,{image_b64}"},
                {"text": prompt},
            ],
        },
    ]

    response = dashscope.MultiModalConversation.call(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.2,
    )

    if response.status_code != 200:
        code = getattr(response, "code", "unknown")
        msg = getattr(response, "message", "error")
        return f"Qwen erreur ({code}): {msg}"

    content = response.output.choices[0].message.content
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return " ".join(part for part in text_parts if part).strip()
    return str(content)


def call_qwen_chat(
    prompt: str,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 220,
    temperature: float = 0.2,
) -> str:
    if not dashscope.api_key:
        return "DASHSCOPE_API_KEY non configuree."

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    response = dashscope.Generation.call(
        model=QWEN_CHAT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if response.status_code != 200:
        code = getattr(response, "code", "unknown")
        msg = getattr(response, "message", "error")
        return f"Qwen chat erreur ({code}): {msg}"

    try:
        content = response.output.text
        return content.strip() if isinstance(content, str) else str(content)
    except Exception:
        try:
            return response.output.choices[0].message.content
        except Exception:
            return "Qwen a repondu dans un format inattendu."


def call_qwen_with_visual_context(prompt: str, frames: list[np.ndarray], system_prompt: str | None = None) -> str:
    if not frames:
        return "Je n'ai rien a analyser pour le moment."

    sheet = build_frame_contact_sheet(frames, cols=2, max_frames=min(len(frames), 4))
    image_b64 = to_base64_jpg(sheet)
    visual_prompt = (
        "Analyse les frames de surveillance et reponds de facon concise. "
        "Dis ce que tu vois, si c'est normal ou suspect, et donne une recommandation."
    )
    if prompt.strip():
        visual_prompt = f"{visual_prompt}\nDemande utilisateur: {prompt.strip()}"
    return call_qwen_dashscope(image_b64=image_b64, prompt=visual_prompt, max_tokens=220, model=QWEN_MODEL)


def is_visual_request(message: str) -> bool:
    text = message.lower()
    keywords = [
        "analyse",
        "environment",
        "environnement",
        "scene",
        "scène",
        "vois",
        "voir",
        "regarde",
        "observ",
        "camera",
        "caméra",
        "image",
        "video",
        "vidéo",
        "frame",
    ]
    return any(keyword in text for keyword in keywords)


def remember_media(kind: str, frame: np.ndarray | None = None, frames: list[np.ndarray] | None = None, note: str | None = None, annotated_video: str | None = None) -> None:
    global LAST_MEDIA_KIND, LAST_IMAGE_FRAME, LAST_ANNOTATED_IMAGE, LAST_ANNOTATED_VIDEO, LAST_MEDIA_NOTE, RECENT_FRAMES
    LAST_MEDIA_KIND = kind
    if frame is not None:
        LAST_IMAGE_FRAME = frame.copy()
        LAST_ANNOTATED_IMAGE = frame.copy()
    if frames is not None:
        RECENT_FRAMES.extend([f.copy() for f in frames])
        RECENT_FRAMES = RECENT_FRAMES[-12:]
    if note is not None:
        LAST_MEDIA_NOTE = note
    if annotated_video is not None:
        LAST_ANNOTATED_VIDEO = annotated_video


def recent_visual_context() -> list[np.ndarray]:
    if RECENT_FRAMES:
        return RECENT_FRAMES[-8:]
    if LAST_ANNOTATED_IMAGE is not None:
        return [LAST_ANNOTATED_IMAGE]
    if LAST_IMAGE_FRAME is not None:
        return [LAST_IMAGE_FRAME]
    return []


def make_data_url_from_path(path: str | None) -> str | None:
    if not path:
        return None
    return artifact_url(path)


def image_to_data_url(frame: np.ndarray | None) -> str | None:
    if frame is None:
        return None
    return f"data:image/jpeg;base64,{to_base64_jpg(frame)}"


def save_annotated_video(frames: list[np.ndarray], fps: float = 5.0, prefix: str = "analyse") -> str | None:
    if not frames:
        return None
    out_dir = PROCESSED_DIR / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{os.urandom(6).hex()}.mp4"
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for frame in frames:
        writer.write(frame)
    writer.release()
    return str(path)


def artifact_url(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path).expanduser()
    if not file_path.is_absolute():
        file_path = (BASE_DIR / file_path).resolve()
    else:
        file_path = file_path.resolve()
    try:
        relative = file_path.relative_to(BASE_DIR.resolve())
    except ValueError:
        relative = Path(file_path.name)
    return f"/artifacts/{relative.as_posix()}"


def audio_url_from_path(path: Path | None) -> str | None:
    if not path:
        return None
    return artifact_url(str(path))


def serialise_alert(alert: dict, source: str | None = None, frame: int | None = None) -> dict[str, Any]:
    payload = {
        "type": "alert",
        "source": source or "system",
        "frame": frame,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "niveau": alert.get("niveau", "INFO"),
        "priorite": int(alert.get("priorite", 0)),
        "message": alert.get("message", ""),
        "classes_detectees": alert.get("classes_detectees", []),
    }
    return payload


async def broadcast_live_event(payload: dict[str, Any]) -> None:
    if not LIVE_CONNECTIONS:
        return
    stale: list[WebSocket] = []
    for websocket in list(LIVE_CONNECTIONS):
        try:
            await websocket.send_json(payload)
        except Exception:
            stale.append(websocket)
    for websocket in stale:
        LIVE_CONNECTIONS.discard(websocket)


def save_alert_and_broadcast(alert: dict, class_ids: list[int], *, photo_path=None, video_path=None, source: str | None = None, frame: int | None = None) -> int:
    alert_id = save_alert(alert, class_ids, photo_path=photo_path, video_path=video_path)
    try:
        payload = serialise_alert(alert, source=source, frame=frame)
        payload["alert_id"] = alert_id
        payload["classes"] = alert.get("classes_detectees", [])
        asyncio.create_task(broadcast_live_event(payload))
    except Exception:
        pass
    return alert_id


def analyze_frame_payload(
    frame: np.ndarray,
    *,
    threshold: float = 0.1,
    save_evidence: bool = True,
    run_qwen: bool = True,
    response_mode: str = "text",
    source: str = "upload",
    filename: str | None = None,
    qwen_prompt: str | None = None,
) -> dict[str, Any]:
    detector = get_detector(threshold=float(threshold))
    boxes, scores, class_ids = detector.detect(frame)
    annotated = detector.draw_results(frame, boxes, scores, class_ids)
    alerte = get_alerte(class_ids)

    evidence_path = None
    if save_evidence and alerte["priorite"] >= 2:
        evidence_path = save_photo(annotated, niveau=alerte["niveau"])
        save_alert_and_broadcast(alerte, class_ids, photo_path=evidence_path, source=source)

    qwen_summary = None
    escalate = should_escalate_to_qwen(class_ids, alerte)
    if run_qwen and escalate:
        try:
            b64 = to_base64_jpg(annotated)
            qwen_summary = call_qwen_dashscope(
                image_b64=b64,
                prompt=qwen_prompt
                or (
                    "Analyse cette scene de surveillance. "
                    "Donne niveau de risque (faible/moyen/eleve), "
                    "resume chronologique court, et action recommandee."
                ),
            )
        except Exception as exc:
            qwen_summary = f"Qwen indisponible: {exc}"

    remember_media(
        kind=source,
        frame=frame,
        frames=[annotated],
        note=qwen_summary,
    )

    voice_path = None
    if str(response_mode).strip().lower() == "voice":
        try:
            voice_source = qwen_summary or alerte["message"]
            voice_path = text_to_speech_file(voice_source, prefix=source)
        except Exception:
            voice_path = None

    return {
        "alert": alerte,
        "detections": summarize_detections(class_ids, scores),
        "boxes_xyxy": boxes,
        "evidence_photo": str(evidence_path) if evidence_path else None,
        "preview_image": image_to_data_url(annotated),
        "qwen_summary": qwen_summary,
        "qwen_escalated": escalate,
        "filename": filename,
        "audio_url": audio_url_from_path(voice_path),
    }


app = FastAPI(title=APP_TITLE, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/artifacts", StaticFiles(directory=str(BASE_DIR)), name="artifacts")

@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return f"""
    <!doctype html>
    <html lang="fr">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{APP_TITLE}</title>
      <style>
        :root {{
          --bg: #0b1120;
          --panel: #111827;
          --panel2: #0f172a;
          --border: #243244;
          --accent: #38bdf8;
          --text: #e5eefb;
          --muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: Inter, Segoe UI, Arial, sans-serif;
          background: radial-gradient(circle at top, #122038 0, #0b1120 45%, #050816 100%);
          color: var(--text);
        }}
        .wrap {{
          max-width: 980px;
          margin: 0 auto;
          padding: 24px 18px 44px;
        }}
        .hero, .card {{
          background: rgba(17, 24, 39, 0.92);
          border: 1px solid var(--border);
          border-radius: 12px;
          backdrop-filter: blur(8px);
        }}
        .hero {{
          padding: 18px;
          margin-bottom: 16px;
        }}
        .grid {{
          display: grid;
          grid-template-columns: 1fr;
          gap: 16px;
          align-items: start;
        }}
        .control-group {{
          display: grid;
          gap: 10px;
        }}
        .toolbar {{
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          align-items: center;
        }}
        .segment {{
          display: inline-flex;
          gap: 8px;
          flex-wrap: wrap;
        }}
        .seg {{
          border: 1px solid var(--border);
          background: #0b1324;
          color: var(--text);
          border-radius: 999px;
          padding: 9px 14px;
          font-weight: 700;
          cursor: pointer;
        }}
        .seg.active {{
          background: var(--accent);
          color: #06131f;
          border-color: transparent;
        }}
        .panel-inline {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }}
        .stack {{
          display: grid;
          gap: 16px;
        }}
        .card {{
          padding: 16px;
        }}
        .row {{
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          align-items: center;
        }}
        .btn {{
          background: var(--accent);
          color: #06131f;
          border: 0;
          border-radius: 10px;
          padding: 11px 16px;
          font-weight: 700;
          cursor: pointer;
        }}
        .btn.secondary {{
          background: #1f2937;
          color: var(--text);
          border: 1px solid #334155;
        }}
        .field {{
          width: 100%;
          background: var(--panel2);
          color: var(--text);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 12px;
          outline: none;
        }}
        .small {{ color: var(--muted); font-size: 13px; line-height: 1.4; }}
        .label {{ font-size: 13px; color: var(--muted); margin: 0 0 6px; }}
        pre {{
          margin: 12px 0 0;
          white-space: pre-wrap;
          background: #08101d;
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 14px;
          min-height: 160px;
          overflow: auto;
        }}
        .viewer {{
          margin-top: 12px;
          width: 100%;
          aspect-ratio: 16 / 9;
          min-height: 260px;
          max-height: 420px;
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid var(--border);
          background: linear-gradient(180deg, #050816 0%, #0a1220 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }}
        .viewer::before {{
          content: "Apercu de detection";
          position: absolute;
          top: 12px;
          left: 12px;
          z-index: 2;
          font-size: 12px;
          color: #cbd5e1;
          background: rgba(2, 6, 23, 0.58);
          border: 1px solid rgba(148, 163, 184, 0.25);
          border-radius: 999px;
          padding: 5px 10px;
        }}
        .viewer img,
        .viewer video {{
          width: 100%;
          height: 100%;
          object-fit: contain;
          display: none;
          background: #050816;
        }}
        .viewer.empty .placeholder {{
          display: flex;
        }}
        .placeholder {{
          display: none;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          color: #64748b;
          text-align: center;
          padding: 16px;
          font-size: 14px;
        }}
        a {{ color: var(--accent); text-decoration: none; }}
        .links {{ margin-top: 10px; }}
        .links a {{ margin-right: 14px; }}
        .live-feed {{
          display: grid;
          gap: 8px;
          max-height: 260px;
          overflow: auto;
          margin-top: 12px;
        }}
        .event {{
          border: 1px solid var(--border);
          border-radius: 12px;
          background: #08101d;
          padding: 10px 12px;
          font-size: 13px;
          line-height: 1.45;
        }}
        .event strong {{
          display: block;
          margin-bottom: 3px;
        }}
        .badge {{
          display: inline-block;
          padding: 3px 8px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.02em;
          margin-right: 6px;
        }}
        .badge.info {{ background: rgba(59, 130, 246, 0.18); color: #93c5fd; }}
        .badge.moderate {{ background: rgba(34, 197, 94, 0.16); color: #86efac; }}
        .badge.high {{ background: rgba(249, 115, 22, 0.16); color: #fdba74; }}
        .badge.critical {{ background: rgba(239, 68, 68, 0.16); color: #fca5a5; }}
        .badge.urgency {{ background: rgba(185, 28, 28, 0.24); color: #fecaca; }}
        .history-table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 12px;
          font-size: 13px;
        }}
        .history-table th,
        .history-table td {{
          text-align: left;
          padding: 10px 8px;
          border-bottom: 1px solid rgba(36, 50, 68, 0.9);
          vertical-align: top;
        }}
        .history-table th {{
          color: var(--muted);
          font-size: 12px;
          font-weight: 600;
        }}
        .history-table tr.level-urgency {{ background: rgba(185, 28, 28, 0.12); }}
        .history-table tr.level-critical {{ background: rgba(239, 68, 68, 0.09); }}
        .history-table tr.level-high {{ background: rgba(249, 115, 22, 0.08); }}
        .history-table tr.level-moderate {{ background: rgba(34, 197, 94, 0.06); }}
        .voice-tools {{
          display: grid;
          grid-template-columns: 1fr auto auto;
          gap: 10px;
          align-items: center;
        }}
        .audio-player {{
          width: 100%;
          margin-top: 10px;
        }}
        details.card {{
          padding: 12px 16px;
        }}
        details.card > summary {{
          cursor: pointer;
          list-style: none;
          font-weight: 700;
        }}
        details.card > summary::-webkit-details-marker {{
          display: none;
        }}
        @media (max-width: 980px) {{
          .voice-tools {{ grid-template-columns: 1fr; }}
          .row {{ align-items: stretch; }}
          .row > * {{ flex: 1 1 100%; }}
          .btn {{ width: 100%; }}
          .hero {{ padding: 16px; }}
          .card {{ padding: 14px; }}
          .viewer {{ min-height: 220px; max-height: 340px; }}
          .panel-inline {{ grid-template-columns: 1fr; }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <section class="hero">
          <h1 style="margin:0 0 8px;">{APP_TITLE}</h1>
          <div class="small">YOLO detecte d'abord, Qwen comprend la scene ensuite, et le systeme t'aide a superviser en temps reel.</div>
          <div class="links">
            <a href="/docs">Documentation API</a>
            <a href="/health">Etat du service</a>
          </div>
          <div class="row" style="margin-top:14px;">
            <div class="small"><strong id="kpiAlerts">0</strong> alertes totales</div>
            <div class="small"><strong id="kpiUnread">0</strong> non lues</div>
            <div class="small"><strong id="kpiCameras">0</strong> cameras actives</div>
            <div class="small"><strong id="kpiEvidences">0</strong> preuves</div>
          </div>
        </section>

        <section class="grid">
          <div class="stack">
            <div class="card">
              <h2 style="margin-top:0;">Analyse</h2>
              <div class="small">Un seul fichier d'entree. Tu mets une photo ou une video, puis tu lances. Si YOLO voit quelque chose, la frame part a Qwen. Sinon, au bout de N frames calmes, Qwen regarde le bloc et comprend la scene.</div>
              <div class="control-group" style="margin-top:14px;">
                <div>
                  <div class="label">Source</div>
                  <div class="segment" id="sourceSegment">
                    <button class="seg active" id="sourceUploadBtn" onclick="setSourceMode('upload')">Photo / video</button>
                    <button class="seg" id="sourceWebcamBtn" onclick="setSourceMode('webcam')">Webcam</button>
                    <button class="seg" id="sourceSurveillanceBtn" onclick="setSourceMode('surveillance')">Camera de surveillance</button>
                  </div>
                </div>
                <div>
                  <div class="label">Sortie</div>
                  <div class="segment" id="responseSegment">
                    <button class="seg active" id="responseTextBtn" onclick="setResponseMode('text')">Texte</button>
                    <button class="seg" id="responseVoiceBtn" onclick="setResponseMode('voice')">Voix</button>
                  </div>
                </div>
              </div>
              <div id="uploadBlock" style="margin-top:14px;">
                <div class="label">Photo ou video</div>
                <input id="mediaFile" class="field" type="file" accept="image/*,video/*">
              </div>
              <div id="liveBlock" style="display:none; margin-top:14px;">
                <div class="small" id="liveModeLabel">Mode live.</div>
                <div class="row" style="margin-top:12px;">
                  <button class="btn" onclick="startLiveSession()">Demarrer</button>
                  <button class="btn secondary" onclick="stopLiveSession()">Arreter</button>
                </div>
              </div>
              <div class="row" style="margin-top:12px;">
                <div style="min-width:160px; flex:1;">
                  <div class="label">Seuil YOLO</div>
                  <input id="threshold" class="field" type="number" step="0.05" min="0.1" max="0.95" value="0.1">
                </div>
                <div style="min-width:200px; flex:1;">
                  <div class="label">Frames calmes avant Qwen</div>
                  <input id="cleanFrames" class="field" type="number" step="1" min="1" max="60" value="6">
                </div>
                <button class="btn" onclick="launchAnalysis()">Lancer</button>
              </div>
              <div id="viewer" class="viewer empty">
                <div class="placeholder" id="viewerPlaceholder">L'aperçu apparaitra ici apres analyse.</div>
                <img id="previewImg" alt="aperçu annoté">
                <video id="previewVideo" controls></video>
              </div>
              <pre id="analysisResult">En attente d'une analyse.</pre>
              <audio id="analysisAudio" class="audio-player" controls style="display:none"></audio>
            </div>

            <div class="card">
              <h2 style="margin-top:0;">Historique des alertes</h2>
              <div class="small">Les derniers evenements detectes par le systeme. Le niveau de danger est visible directement dans la ligne.</div>
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Niveau</th>
                    <th>Message</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody id="alertsTableBody">
                  <tr><td colspan="4" class="small">Chargement...</td></tr>
                </tbody>
              </table>
            </div>

            <div class="card">
              <h2 style="margin-top:0;">Webcam directe</h2>
              <div class="small">La camera tourne en direct, envoie des frames au moteur d'analyse, et garde les derniers instants pour Qwen.</div>
              <div id="webcamFrame" class="viewer" style="margin-top:14px; min-height:240px;">
                <div class="placeholder" id="webcamPlaceholder">Aucune camera active pour le moment.</div>
                <video id="webcamPreview" autoplay muted playsinline></video>
              </div>
              <div class="row" style="margin-top:12px;">
                <button class="btn" onclick="startLiveSession()">Demarrer la camera</button>
                <button class="btn secondary" onclick="stopLiveSession()">Arreter</button>
              </div>
              <div class="small" id="webcamStatus" style="margin-top:8px;">Session inactive.</div>
            </div>
          </div>

          <div class="stack">
            <div class="card">
              <h2 style="margin-top:0;">Chat Qwen</h2>
              <div class="small">Exemples: "analyse l'environnement", "que vois-tu ?", "resume le risque". Si aucune frame recente n'existe, Qwen dira qu'il n'a rien a faire.</div>
              <div style="margin-top:14px;">
                <div class="label">Commande</div>
                <textarea id="chatMessage" class="field" rows="7" placeholder="Analyse l'environnement..."></textarea>
              </div>
              <div class="row" style="margin-top:12px;">
                <button class="btn" onclick="sendChat()">Parler</button>
                <button class="btn secondary" onclick="resetChat()">Effacer</button>
              </div>
              <pre id="chatResult">Aucun message.</pre>
              <audio id="chatAudio" class="audio-player" controls style="display:none"></audio>
            </div>

            <div class="card">
              <h2 style="margin-top:0;">Voix</h2>
              <div class="small">Tu peux dicter une commande, la transcrire avec Vosk, puis l'envoyer a Qwen. Le retour vocal est aussi joue si disponible.</div>
              <div style="margin-top:14px;">
                <div class="label">Audio</div>
                <input id="voiceFile" class="field" type="file" accept="audio/*">
              </div>
              <div class="voice-tools" style="margin-top:12px;">
                <button class="btn" onclick="transcribeVoice()">Transcrire</button>
                <button class="btn secondary" onclick="toggleRecording(this)">Enregistrer</button>
                <button class="btn secondary" onclick="sendVoiceToQwen()">Envoyer</button>
              </div>
              <div class="small" id="recordStatus" style="margin-top:8px;">Aucun enregistrement.</div>
              <pre id="voiceResult">Aucun texte pour le moment.</pre>
              <audio id="voiceAudio" class="audio-player" controls style="display:none"></audio>
            </div>

            <div class="card">
              <h2 style="margin-top:0;">Flux temps reel</h2>
              <div class="small">Les alertes arrivent ici en direct via WebSocket. Tu vois le niveau de danger, la source et le dernier contexte analyse.</div>
              <div id="liveFeed" class="live-feed">
                <div class="event">Connexion au flux en attente...</div>
              </div>
            </div>

            <div class="card">
              <h2 style="margin-top:0;">Commandes utiles</h2>
              <div class="small">
                <div>/analyze/frame pour une image</div>
                <div>/analyze/video pour une video</div>
                <div>/chat pour parler avec Qwen</div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <script>
        const uiState = {{
          sourceMode: "upload",
          responseMode: "text",
        }};

        const liveState = {{
          socket: null,
          recorder: null,
          recordChunks: [],
          recordedBlob: null,
          webcamStream: null,
          webcamTimer: null,
          audioRecorder: null,
          audioStream: null,
          audioChunks: [],
          running: false,
        }};

        function escapeHtml(text) {{
          return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
        }}

        function levelClass(level) {{
          const value = String(level || "").toUpperCase();
          if (value === "URGENCE") return "urgency";
          if (value === "CRITIQUE") return "critical";
          if (value === "ELEVE") return "high";
          if (value === "MODERE") return "moderate";
          return "info";
        }}

        function setActiveButton(containerSelector, activeId) {{
          document.querySelectorAll(`${{containerSelector}} .seg`).forEach((button) => {{
            button.classList.toggle("active", button.id === activeId);
          }});
        }}

        function setSourceMode(mode) {{
          uiState.sourceMode = mode;
          setActiveButton("#sourceSegment", mode === "upload" ? "sourceUploadBtn" : mode === "webcam" ? "sourceWebcamBtn" : "sourceSurveillanceBtn");
          document.getElementById("uploadBlock").style.display = mode === "upload" ? "block" : "none";
          document.getElementById("liveBlock").style.display = mode === "upload" ? "none" : "block";
          document.getElementById("liveModeLabel").textContent = mode === "webcam"
            ? "Mode live: webcam du navigateur."
            : "Mode live: camera de surveillance (simulation via camera du navigateur pour le test).";
        }}

        function setResponseMode(mode) {{
          uiState.responseMode = mode;
          setActiveButton("#responseSegment", mode === "text" ? "responseTextBtn" : "responseVoiceBtn");
          const visible = mode === "voice";
          document.getElementById("analysisAudio").style.display = visible ? "block" : "none";
          document.getElementById("chatAudio").style.display = visible ? "block" : "none";
          document.getElementById("voiceAudio").style.display = visible ? "block" : "none";
        }}

        function maybePlayAudio(audioId, url) {{
          const player = document.getElementById(audioId);
          if (!url || uiState.responseMode !== "voice") {{
            player.style.display = "none";
            player.removeAttribute("src");
            return;
          }}
          player.src = url;
          player.style.display = "block";
          player.load();
          player.play().catch(() => {{}});
        }}

        function clearAnalysis() {{
          const viewer = document.getElementById("viewer");
          viewer.classList.add("empty");
          document.getElementById("viewerPlaceholder").style.display = "flex";
          document.getElementById("previewImg").style.display = "none";
          document.getElementById("previewVideo").style.display = "none";
          document.getElementById("analysisResult").textContent = "En attente d'une analyse.";
          document.getElementById("analysisAudio").style.display = "none";
          document.getElementById("analysisAudio").removeAttribute("src");
        }}

        function renderRecentAlerts(alerts) {{
          const tbody = document.getElementById("alertsTableBody");
          if (!alerts || !alerts.length) {{
            tbody.innerHTML = '<tr><td colspan="4" class="small">Aucune alerte recente.</td></tr>';
            return;
          }}
          tbody.innerHTML = alerts.map((item) => {{
            const level = escapeHtml(item.niveau || "INFO");
            const cls = levelClass(item.niveau);
            const source = escapeHtml(item.photo_path ? "image" : (item.video_path ? "video" : "system"));
            const timestamp = escapeHtml((item.timestamp || "").slice(11, 19) || item.timestamp || "");
            return `
              <tr class="level-${{cls}}">
                <td>${{timestamp}}</td>
                <td><span class="badge ${{cls}}">${{level}}</span></td>
                <td>${{escapeHtml(item.message || "")}}</td>
                <td>${{source}}</td>
              </tr>
            `;
          }}).join("");
        }}

        function renderLiveEvent(title, text, level, source) {{
          const feed = document.getElementById("liveFeed");
          const cls = levelClass(level);
          const levelLabel = escapeHtml(level || "INFO");
          const sourceLabel = escapeHtml(source || "system");
          const item = document.createElement("div");
          item.className = "event";
          item.innerHTML = `
            <strong><span class="badge ${{cls}}">${{levelLabel}}</span>${{escapeHtml(title || "Evenement")}}</strong>
            <div>${{escapeHtml(text || "")}}</div>
            <div class="small" style="margin-top:4px;">Source: ${{sourceLabel}}</div>
          `;
          feed.prepend(item);
          while (feed.children.length > 8) {{
            feed.removeChild(feed.lastChild);
          }}
        }}

        function setAudio(audioId, url) {{
          const player = document.getElementById(audioId);
          if (!url) {{
            player.removeAttribute("src");
            player.style.display = "none";
            return;
          }}
          player.src = url;
          player.style.display = "block";
          player.load();
        }}

        async function refreshDashboard() {{
          try {{
            const [statsResponse, alertsResponse] = await Promise.all([
              fetch("/stats"),
              fetch("/alerts/recent?limit=8"),
            ]);
            const stats = await statsResponse.json();
            const alertData = await alertsResponse.json();
            document.getElementById("kpiAlerts").textContent = stats.total_alerts ?? 0;
            document.getElementById("kpiUnread").textContent = stats.unread ?? 0;
            document.getElementById("kpiCameras").textContent = stats.active_cameras ?? 0;
            document.getElementById("kpiEvidences").textContent = stats.evidences ?? 0;
            renderRecentAlerts(alertData.alerts || []);
          }} catch (error) {{
            renderLiveEvent("Dashboard", "Impossible de charger les donnees.", "INFO", "system");
          }}
        }}

        function connectLiveSocket() {{
          const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
          const socket = new WebSocket(`${{protocol}}//${{window.location.host}}/ws/live`);
          liveState.socket = socket;

          socket.onopen = () => {{
            renderLiveEvent("Flux", "Connexion temps reel ouverte.", "MODERE", "websocket");
          }};

          socket.onmessage = (event) => {{
            let data = null;
            try {{
              data = JSON.parse(event.data);
            }} catch (_error) {{
              return;
            }}

            if (data.type === "ready") {{
              if (data.stats) {{
                document.getElementById("kpiAlerts").textContent = data.stats.total_alerts ?? 0;
                document.getElementById("kpiUnread").textContent = data.stats.unread ?? 0;
                document.getElementById("kpiCameras").textContent = data.stats.active_cameras ?? 0;
                document.getElementById("kpiEvidences").textContent = data.stats.evidences ?? 0;
              }}
              if (data.alerts) {{
                renderRecentAlerts(data.alerts);
              }}
              renderLiveEvent("Flux pret", "Le serveur a accepte la connexion.", "MODERE", "websocket");
              return;
            }}

            if (data.type === "alert") {{
              renderLiveEvent("Alerte", data.message || "Nouvelle alerte detectee.", data.niveau, data.source);
              refreshDashboard();
              return;
            }}

            if (data.type === "detection") {{
              renderLiveEvent("Detection", data.qwen_summary || data.alert?.message || "Detection analysee.", data.alert?.niveau, data.source);
              refreshDashboard();
              return;
            }}

            if (data.type === "video_summary") {{
              renderLiveEvent("Video", "Resume video termine.", data.alerts?.[0]?.niveau || "MODERE", data.source);
              refreshDashboard();
              return;
            }}
          }};

          socket.onclose = () => {{
            renderLiveEvent("Flux", "Connexion perdue, reconnexion en cours...", "INFO", "websocket");
            setTimeout(connectLiveSocket, 3000);
          }};

          socket.onerror = () => {{
            renderLiveEvent("Flux", "Erreur de connexion temps reel.", "INFO", "websocket");
          }};
        }}

        function currentVoiceFile() {{
          const input = document.getElementById("voiceFile");
          if (input.files && input.files[0]) {{
            return input.files[0];
          }}
          if (liveState.recordedBlob) {{
            return new File([liveState.recordedBlob], "recording.webm", {{ type: liveState.recordedBlob.type || "audio/webm" }});
          }}
          return null;
        }}

        function looksLikeVoiceCommand(text) {{
          const value = String(text || "").toLowerCase();
          return [
            "analyse",
            "analyser",
            "regarde",
            "observ",
            "decris",
            "décris",
            "resume",
            "résume",
            "que vois",
            "quel est",
            "danger",
          ].some((keyword) => value.includes(keyword));
        }}

        async function sendChat(overrideMessage) {{
          const input = document.getElementById("chatMessage");
          const message = String(overrideMessage || input.value).trim();
          const result = document.getElementById("chatResult");
          if (!message) {{
            result.textContent = "Ecris une commande ou une question.";
            return;
          }}

          const form = new FormData();
          form.append("message", message);
          form.append("system_prompt", "Tu es un assistant de surveillance. Si des frames recentes existent, analyse-les. Sinon repond simplement qu'il n'y a rien a faire.");
          form.append("max_tokens", "220");
          form.append("response_mode", uiState.responseMode);

          result.textContent = "Qwen repond...";
          const response = await fetch("/chat", {{
            method: "POST",
            body: form
          }});
          const data = await response.json();
          result.textContent = data.answer || JSON.stringify(data, null, 2);
          maybePlayAudio("chatAudio", data.audio_url || null);
          return data;
        }}

        async function captureAndSendLiveFrame() {{
          if (!liveState.running || !liveState.webcamStream) return;
          const video = document.getElementById("webcamPreview");
          if (!video.videoWidth || !video.videoHeight) {{
            setTimeout(captureAndSendLiveFrame, 400);
            return;
          }}
          const canvas = document.createElement("canvas");
          canvas.width = video.videoWidth || 640;
          canvas.height = video.videoHeight || 360;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
          if (!blob) return;

          const form = new FormData();
          form.append("file", blob, "webcam.jpg");
          form.append("threshold", document.getElementById("threshold").value);
          form.append("save_evidence", "true");
          form.append("run_qwen", "true");
          form.append("response_mode", uiState.responseMode);
          form.append("source_mode", uiState.sourceMode);

          try {{
            const response = await fetch("/live/frame", {{
              method: "POST",
              body: form,
            }});
            const data = await response.json();
            if (data.preview_image) {{
              const img = document.getElementById("previewImg");
              const videoPreview = document.getElementById("previewVideo");
              const viewer = document.getElementById("viewer");
              document.getElementById("viewerPlaceholder").style.display = "none";
              img.src = data.preview_image;
              img.style.display = "block";
              videoPreview.style.display = "none";
              viewer.classList.remove("empty");
            }}
            if (data.audio_url) {{
              maybePlayAudio("analysisAudio", data.audio_url);
            }}
            if (data.alert) {{
              document.getElementById("analysisResult").textContent = JSON.stringify(data, null, 2);
            }}
          }} catch (_error) {{
            document.getElementById("webcamStatus").textContent = "Erreur d'envoi d'une frame au serveur.";
          }}
        }}

        async function handleVoiceChunk(blob) {{
          if (!blob || blob.size === 0) return;
          const form = new FormData();
          form.append("file", blob, "voice_chunk.webm");
          try {{
            const response = await fetch("/speech-to-text", {{
              method: "POST",
              body: form
            }});
            const data = await response.json();
            const transcript = String(data.transcript || "").trim();
            if (!transcript) return;
            document.getElementById("voiceResult").textContent = transcript;
            if (looksLikeVoiceCommand(transcript)) {{
              document.getElementById("chatMessage").value = transcript;
              await sendChat(transcript);
            }}
          }} catch (_error) {{
            document.getElementById("recordStatus").textContent = "Transcription vocale en erreur.";
          }}
        }}

        async function startAudioLoop(stream) {{
          if (!stream) return;
          liveState.audioStream = stream;
          liveState.audioRecorder = new MediaRecorder(stream);
          liveState.audioRecorder.ondataavailable = (event) => {{
            if (event.data && event.data.size > 0) {{
              handleVoiceChunk(event.data);
            }}
          }};
          liveState.audioRecorder.onstop = () => {{
            liveState.audioChunks = [];
          }};
          liveState.audioRecorder.start(4000);
        }}

        async function startLiveSession() {{
          if (liveState.running) return;
          const status = document.getElementById("webcamStatus");
          const placeholder = document.getElementById("webcamPlaceholder");
          const video = document.getElementById("webcamPreview");
          try {{
            const stream = await navigator.mediaDevices.getUserMedia({{ video: true, audio: true }});
            liveState.running = true;
            liveState.webcamStream = stream;
            video.srcObject = stream;
            video.style.display = "block";
            placeholder.style.display = "none";
            status.textContent = uiState.sourceMode === "surveillance"
              ? "Camera de surveillance activee. Le systeme analyse les frames et ecoute la voix."
              : "Camera activee. Le systeme analyse les frames et ecoute la voix.";
            document.getElementById("liveModeLabel").textContent = uiState.sourceMode === "surveillance"
              ? "Mode live: camera de surveillance en cours."
              : "Mode live: webcam en cours.";
            await startAudioLoop(stream);
            captureAndSendLiveFrame();
            liveState.webcamTimer = setInterval(captureAndSendLiveFrame, 1200);
          }} catch (error) {{
            status.textContent = "Impossible d'activer la camera ou le micro.";
          }}
        }}

        function stopLiveSession() {{
          liveState.running = false;
          if (liveState.webcamTimer) {{
            clearInterval(liveState.webcamTimer);
            liveState.webcamTimer = null;
          }}
          if (liveState.audioRecorder && liveState.audioRecorder.state === "recording") {{
            liveState.audioRecorder.stop();
          }}
          if (liveState.webcamStream) {{
            liveState.webcamStream.getTracks().forEach((track) => track.stop());
            liveState.webcamStream = null;
          }}
          if (liveState.audioStream) {{
            liveState.audioStream.getTracks().forEach((track) => track.stop());
            liveState.audioStream = null;
          }}
          document.getElementById("webcamStatus").textContent = "Session arretee.";
          document.getElementById("webcamPreview").srcObject = null;
          document.getElementById("webcamPlaceholder").style.display = "flex";
          document.getElementById("liveModeLabel").textContent = "Mode live.";
        }}

        async function launchAnalysis() {{
          const fileInput = document.getElementById("mediaFile");
          const file = fileInput.files[0];
          const result = document.getElementById("analysisResult");
          const img = document.getElementById("previewImg");
          const video = document.getElementById("previewVideo");
          const viewer = document.getElementById("viewer");
          const placeholder = document.getElementById("viewerPlaceholder");
          if (!file) {{
            result.textContent = "Choisis une image ou une video.";
            return;
          }}

          const form = new FormData();
          form.append("file", file);
          form.append("threshold", document.getElementById("threshold").value);
          form.append("save_evidence", "true");
          form.append("run_qwen", "true");
          form.append("qwen_clean_frame_threshold", document.getElementById("cleanFrames").value);

          img.style.display = "none";
          video.style.display = "none";
          placeholder.style.display = "none";
          viewer.classList.remove("empty");
          result.textContent = "Analyse en cours...";
          maybePlayAudio("analysisAudio", null);

          const endpoint = file.type.startsWith("video/") ? "/analyze/video" : "/analyze/frame";
          const response = await fetch(endpoint, {{
            method: "POST",
            body: form
          }});
          const data = await response.json();
          result.textContent = JSON.stringify(data, null, 2);

          if (data.preview_image) {{
            img.src = data.preview_image;
            img.style.display = "block";
          }} else if (data.evidence_photo) {{
            img.src = data.evidence_photo;
            img.style.display = "block";
          }}

          if (data.annotated_video_url) {{
            video.src = data.annotated_video_url;
            video.style.display = "block";
          }}

          if (data.audio_url) {{
            maybePlayAudio("analysisAudio", data.audio_url);
          }}

          if (!data.preview_image && !data.evidence_photo && !data.annotated_video_url) {{
            placeholder.textContent = "Aucun rendu visuel disponible pour cette analyse.";
            placeholder.style.display = "flex";
            viewer.classList.add("empty");
          }}

          await refreshDashboard();
        }}

        function resetChat() {{
          document.getElementById("chatMessage").value = "";
          document.getElementById("chatResult").textContent = "Aucun message.";
          maybePlayAudio("chatAudio", null);
        }}

        async function transcribeVoice() {{
          const file = currentVoiceFile();
          const result = document.getElementById("voiceResult");
          if (!file) {{
            result.textContent = "Ajoute un fichier audio ou enregistre une voix.";
            return;
          }}

          const form = new FormData();
          form.append("file", file, file.name || "voice_input.webm");
          form.append("response_mode", uiState.responseMode);
          result.textContent = "Transcription en cours...";

          const response = await fetch("/speech-to-text", {{
            method: "POST",
            body: form
          }});
          const data = await response.json();
          result.textContent = data.transcript || "Aucun texte reconnu.";
          document.getElementById("chatMessage").value = data.transcript || "";
          maybePlayAudio("voiceAudio", null);
        }}

        async function sendVoiceToQwen() {{
          const file = currentVoiceFile();
          if (!file) {{
            document.getElementById("voiceResult").textContent = "Ajoute un audio ou enregistre une voix avant d'envoyer.";
            return;
          }}

          await transcribeVoice();
          const transcript = document.getElementById("voiceResult").textContent.trim();
          if (!transcript || transcript === "Aucun texte reconnu.") {{
            return;
          }}
          document.getElementById("chatMessage").value = transcript;
          await sendChat();
        }}

        async function toggleRecording(button) {{
          const status = document.getElementById("recordStatus");
          if (!navigator.mediaDevices || !window.MediaRecorder) {{
            status.textContent = "Enregistrement non disponible dans ce navigateur.";
            return;
          }}

          if (liveState.recorder && liveState.recorder.state === "recording") {{
            liveState.recorder.stop();
            if (button) button.textContent = "Enregistrer";
            return;
          }}

          const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
          liveState.recordChunks = [];
          liveState.recorder = new MediaRecorder(stream);
          liveState.recordedBlob = null;
          liveState.recorder.ondataavailable = (e) => {{
            if (e.data && e.data.size > 0) {{
              liveState.recordChunks.push(e.data);
            }}
          }};
          liveState.recorder.onstop = () => {{
            const blob = new Blob(liveState.recordChunks, {{ type: liveState.recorder.mimeType || "audio/webm" }});
            liveState.recordedBlob = blob;
            status.textContent = "Enregistrement pret a transcrire.";
            if (button) button.textContent = "Enregistrer";
            stream.getTracks().forEach((track) => track.stop());
          }};
          liveState.recorder.start();
          status.textContent = "Enregistrement en cours...";
          if (button) button.textContent = "Arreter";
        }}

        window.addEventListener("load", () => {{
          setSourceMode(uiState.sourceMode);
          setResponseMode(uiState.responseMode);
          refreshDashboard();
          connectLiveSocket();
        }});
      </script>
    </body>
    </html>
    """


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": APP_TITLE,
        "qwen_dashscope_configured": bool(dashscope.api_key),
        "qwen_model": QWEN_MODEL,
        "qwen_chat_model": QWEN_CHAT_MODEL,
    }


@app.get("/stats")
def stats() -> dict:
    return get_dashboard_stats()


@app.get("/alerts/recent")
def recent_alerts(limit: int = 10) -> dict:
    safe_limit = max(1, min(50, int(limit)))
    return {"alerts": get_alerts(limit=safe_limit)}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    LIVE_CONNECTIONS.add(websocket)
    try:
        await websocket.send_json(
            {
                "type": "ready",
                "service": APP_TITLE,
                "stats": get_dashboard_stats(),
                "alerts": get_alerts(limit=5),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        LIVE_CONNECTIONS.discard(websocket)


@app.post("/speech-to-text")
async def speech_to_text(file: UploadFile = File(...)) -> dict:
    temp_dir = Path("evidences") / "tmp_audio"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / (file.filename or "speech_input")
    temp_path.write_bytes(await file.read())
    try:
        transcript = transcribe_audio_file(temp_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "filename": file.filename,
        "transcript": transcript,
    }


@app.post("/live/frame")
async def live_frame(
    file: UploadFile = File(...),
    threshold: float = Form(0.1),
    save_evidence: bool = Form(True),
    run_qwen: bool = Form(True),
    response_mode: str = Form("text"),
    source_mode: str = Form("webcam"),
) -> dict:
    raw = await file.read()
    try:
        frame = decode_image_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        source_label = "camera de surveillance" if str(source_mode).strip().lower() == "surveillance" else "webcam"
        payload = analyze_frame_payload(
            frame,
            threshold=threshold,
            save_evidence=save_evidence,
            run_qwen=run_qwen,
            response_mode=response_mode,
            source=source_mode or "webcam",
            filename=file.filename,
            qwen_prompt=(
                f"Analyse cette frame de {source_label} en temps reel. "
                "Si c'est une menace, dis-le tout de suite. "
                "Sinon decris brievement la scene."
            ),
        )
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    asyncio.create_task(
        broadcast_live_event(
            {
                "type": "detection",
                "source": source_mode or "webcam",
                "filename": file.filename,
                "alert": payload["alert"],
                "qwen_summary": payload["qwen_summary"],
                "preview_image": payload["preview_image"],
            }
        )
    )
    return payload


@app.post("/chat")
async def chat(
    message: str = Form(...),
    system_prompt: str = Form(
        "Tu es un assistant de surveillance. Reponds de maniere courte, claire et operationnelle."
    ),
    temperature: float = Form(0.2),
    max_tokens: int = Form(220),
    response_mode: str = Form("text"),
) -> dict:
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message vide.")

    visual = is_visual_request(message)
    context_frames = recent_visual_context() if visual else []
    if visual and context_frames:
        answer = call_qwen_with_visual_context(message, context_frames, system_prompt=system_prompt)
    elif visual and not context_frames:
        answer = "Je n'ai aucune frame ou video recente a analyser."
    else:
        answer = call_qwen_chat(
            prompt=message,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    voice_path = None
    if str(response_mode).strip().lower() == "voice":
        try:
            voice_path = text_to_speech_file(answer, prefix="chat")
        except Exception:
            voice_path = None
    return {
        "message": message,
        "answer": answer,
        "model": QWEN_CHAT_MODEL,
        "visual_context_used": bool(context_frames),
        "audio_url": audio_url_from_path(voice_path),
    }


@app.post("/analyze/frame")
async def analyze_frame(
    file: UploadFile = File(...),
    threshold: float = Form(0.1),
    save_evidence: bool = Form(True),
    run_qwen: bool = Form(True),
    response_mode: str = Form("text"),
) -> dict:
    raw = await file.read()
    try:
        frame = decode_image_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        payload = analyze_frame_payload(
            frame,
            threshold=threshold,
            save_evidence=save_evidence,
            run_qwen=run_qwen,
            response_mode=response_mode,
            source="image",
            filename=file.filename,
        )
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    asyncio.create_task(
        broadcast_live_event(
            {
                "type": "detection",
                "source": "image",
                "filename": file.filename,
                "alert": payload["alert"],
                "qwen_summary": payload["qwen_summary"],
                "preview_image": payload["preview_image"],
            }
        )
    )
    return payload


@app.post("/analyze/video")
async def analyze_video(
    file: UploadFile = File(...),
    threshold: float = Form(0.1),
    sample_every_n_frames: int = Form(15),
    run_qwen: bool = Form(True),
    qwen_clean_frame_threshold: int = Form(6),
    response_mode: str = Form("text"),
) -> dict:
    temp_dir = Path("evidences") / "tmp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / (file.filename or "upload_video.mp4")
    temp_path.write_bytes(await file.read())

    try:
        detector = get_detector(threshold=float(threshold))
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    cap = cv2.VideoCapture(str(temp_path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Video non lisible.")

    sample_every = max(1, int(sample_every_n_frames))
    clean_threshold = max(1, int(qwen_clean_frame_threshold))
    frame_idx = 0
    sample_idx = 0
    clean_buffer: list[np.ndarray] = []
    annotated_frames: list[np.ndarray] = []
    alerts = []
    qwen_notes = []
    last_voice_text = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % sample_every != 0:
            continue

        sample_idx += 1
        boxes, scores, class_ids = detector.detect(frame)
        alerte = get_alerte(class_ids)
        escalate = should_escalate_to_qwen(class_ids, alerte)
        annotated = detector.draw_results(frame, boxes, scores, class_ids)
        annotated_frames.append(annotated)

        if alerte["priorite"] >= 2:
            clean_buffer.clear()
            alert_photo = save_photo(annotated, niveau=alerte["niveau"])
            save_alert_and_broadcast(
                alerte,
                class_ids,
                photo_path=alert_photo,
                source="video",
                frame=frame_idx,
            )
            alerts.append(
                {
                    "frame": frame_idx,
                    "niveau": alerte["niveau"],
                    "message": alerte["message"],
                    "detections": summarize_detections(class_ids, scores),
                    "evidence_photo": str(alert_photo) if alert_photo else None,
                }
            )

            if run_qwen and escalate:
                try:
                    b64 = to_base64_jpg(annotated)
                    note = call_qwen_dashscope(
                        image_b64=b64,
                        prompt=(
                            "YOLO a detecte une menace. "
                            "Explique la scene, le danger potentiel, et l'action immediate."
                        ),
                    )
                    qwen_notes.append({"frame": frame_idx, "mode": "risk", "note": note})
                    last_voice_text = note
                except Exception as exc:
                    qwen_notes.append({"frame": frame_idx, "mode": "risk", "note": f"Qwen indisponible: {exc}"})
        else:
            clean_buffer.append(frame.copy())
            if len(clean_buffer) >= clean_threshold and run_qwen:
                try:
                    sheet = build_frame_contact_sheet(clean_buffer, cols=2, max_frames=min(clean_threshold, 4))
                    b64 = to_base64_jpg(sheet)
                    note = call_qwen_dashscope(
                        image_b64=b64,
                        prompt=(
                            "YOLO n'a rien detecte pendant plusieurs frames consecutives. "
                            "Analyse la scene et decris si quelque chose semble anormal ou notable."
                        ),
                    )
                    qwen_notes.append({"frame": frame_idx, "mode": "clean_batch", "note": note})
                    last_voice_text = note
                except Exception as exc:
                    qwen_notes.append({"frame": frame_idx, "mode": "clean_batch", "note": f"Qwen indisponible: {exc}"})
                finally:
                    clean_buffer.clear()

    cap.release()

    annotated_video_path = save_annotated_video(annotated_frames, fps=max(3.0, 15.0 / max(1, sample_every)), prefix="annotated_video")
    annotated_video_url = make_data_url_from_path(annotated_video_path) if annotated_video_path else None
    remember_media(
        kind="video",
        frames=annotated_frames,
        note=qwen_notes[-1]["note"] if qwen_notes else None,
        annotated_video=annotated_video_path,
    )

    if clean_buffer and run_qwen:
        try:
            sheet = build_frame_contact_sheet(clean_buffer, cols=2, max_frames=min(len(clean_buffer), 4))
            b64 = to_base64_jpg(sheet)
            note = call_qwen_dashscope(
                image_b64=b64,
                prompt=(
                    "Ces frames de fin de video n'ont pas declenche YOLO. "
                    "Fais une lecture courte de la scene."
                ),
            )
            qwen_notes.append({"frame": frame_idx, "mode": "clean_batch_final", "note": note})
            last_voice_text = note
        except Exception as exc:
            qwen_notes.append({"frame": frame_idx, "mode": "clean_batch_final", "note": f"Qwen indisponible: {exc}"})

    voice_path = None
    if str(response_mode).strip().lower() == "voice":
        try:
            voice_source = last_voice_text or (alerts[-1]["message"] if alerts else "Analyse terminee.")
            voice_path = text_to_speech_file(voice_source, prefix="video")
        except Exception:
            voice_path = None

    asyncio.create_task(
        broadcast_live_event(
            {
                "type": "video_summary",
                "source": "video",
                "filename": file.filename,
                "alerts_count": len(alerts),
                "alerts": alerts[-3:],
                "qwen_notes": qwen_notes[-2:],
                "preview_image": image_to_data_url(annotated_frames[-1]) if annotated_frames else None,
            }
        )
    )

    return {
        "filename": file.filename,
        "samples_processed": sample_idx,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "qwen_notes": qwen_notes,
        "annotated_video_url": annotated_video_url,
        "preview_image": image_to_data_url(annotated_frames[-1]) if annotated_frames else None,
        "audio_url": audio_url_from_path(voice_path),
    }
