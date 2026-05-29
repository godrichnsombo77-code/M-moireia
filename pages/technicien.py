from pathlib import Path

import cv2
import gradio as gr
import pandas as pd

from utils.database import get_cameras
from utils.detection import DEFAULT_MODEL_PATH
from utils.video_recorder import LOGS_DIR, ensure_evidence_dirs


def system_status(threshold: float, save_evidence: bool) -> str:
    model_status = "present" if Path(DEFAULT_MODEL_PATH).exists() else "introuvable"
    save_status = "activee" if save_evidence else "desactivee"
    return (
        "Configuration appliquee.\n"
        f"Seuil de detection : {threshold:.2f}\n"
        f"Sauvegarde des preuves : {save_status}\n"
        f"Modele OpenVINO : {model_status}"
    )


def test_webcam(camera_index: int) -> str:
    cap = cv2.VideoCapture(int(camera_index))
    if cap.isOpened():
        cap.release()
        return f"Webcam {int(camera_index)} disponible."
    return f"Webcam {int(camera_index)} non accessible."


def test_rtsp(rtsp_url: str) -> str:
    if not rtsp_url:
        return "Saisissez une URL RTSP."

    cap = cv2.VideoCapture(rtsp_url)
    if cap.isOpened():
        cap.release()
        return "Flux video accessible."
    return "Impossible d'acceder au flux."


def cameras_dataframe() -> pd.DataFrame:
    cameras = get_cameras()
    if not cameras:
        return pd.DataFrame(columns=["id", "nom", "source", "type", "statut", "derniere connexion"])
    return pd.DataFrame(
        [
            {
                "id": camera["id"],
                "nom": camera["name"],
                "source": camera["source"],
                "type": camera["type"],
                "statut": camera["status"],
                "derniere connexion": camera.get("last_connection") or "",
            }
            for camera in cameras
        ]
    )


def read_logs() -> str:
    ensure_evidence_dirs()
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not logs:
        return "Aucun log disponible."

    content = []
    for path in logs[:5]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        content.append(f"--- {path.name} ---\n{text[-2000:]}")
    return "\n\n".join(content)


def create_technicien_tab():
    with gr.Tab("Technicien"):
        gr.Markdown("## Configuration technique")
        with gr.Row():
            threshold = gr.Slider(0.1, 0.95, value=0.5, step=0.05, label="Seuil de detection")
            save_evidence = gr.Checkbox(value=True, label="Sauvegarde automatique des preuves")
        save_config_btn = gr.Button("Sauvegarder la configuration", variant="primary")
        config_status = gr.Textbox(label="Etat de la configuration", lines=4)

        gr.Markdown("## Cameras")
        cameras_table = gr.Dataframe(label="Cameras enregistrees", interactive=False)
        refresh_cameras = gr.Button("Actualiser les cameras")

        with gr.Row():
            camera_index = gr.Number(value=0, precision=0, label="Index webcam")
            webcam_btn = gr.Button("Tester la webcam")
        webcam_result = gr.Textbox(label="Resultat webcam")

        gr.Markdown("## Flux RTSP")
        rtsp_url = gr.Textbox(label="URL du flux", placeholder="rtsp://adresse:port/stream")
        rtsp_btn = gr.Button("Tester le flux")
        rtsp_result = gr.Textbox(label="Resultat RTSP")

        gr.Markdown("## Logs systeme")
        logs_btn = gr.Button("Lire les logs")
        logs_output = gr.Textbox(label="Logs recents", lines=12)

        save_config_btn.click(system_status, inputs=[threshold, save_evidence], outputs=config_status)
        refresh_cameras.click(cameras_dataframe, outputs=cameras_table)
        webcam_btn.click(test_webcam, inputs=camera_index, outputs=webcam_result)
        rtsp_btn.click(test_rtsp, inputs=rtsp_url, outputs=rtsp_result)
        logs_btn.click(read_logs, outputs=logs_output)

        return cameras_dataframe, cameras_table
