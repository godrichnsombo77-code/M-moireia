from pathlib import Path
import shutil
import subprocess

import cv2
import gradio as gr
import pandas as pd
import plotly.express as px

from utils.alerte import get_alerte, get_class_names
from utils.database import get_alerts, get_dashboard_stats, save_alert, update_alert_status
from utils.detection import ModelNotAvailableError, bgr_to_rgb, get_detector, rgb_to_bgr
from utils.video_recorder import (
    VIDEOS_DIR,
    evidence_groups,
    list_evidence_files,
    make_timestamp,
    save_photo,
    save_video_clip,
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def file_path(file_value) -> Path | None:
    if file_value is None:
        return None
    if isinstance(file_value, str):
        return Path(file_value)
    if isinstance(file_value, dict) and file_value.get("name"):
        return Path(file_value["name"])
    if hasattr(file_value, "name"):
        return Path(file_value.name)
    return None


def format_stats() -> tuple[str, str, str, str, str]:
    stats = get_dashboard_stats()
    return (
        str(stats["alerts_today"]),
        str(stats["unread"]),
        str(stats["active_cameras"]),
        str(stats["evidences"]),
        str(stats["total_alerts"]),
    )


def score_cards_html() -> str:
    stats = get_dashboard_stats()
    cards = [
        ("Alertes aujourd'hui", stats["alerts_today"], "blue"),
        ("Non lues", stats["unread"], "red"),
        ("Cameras actives", stats["active_cameras"], "green"),
        ("Preuves archivees", stats["evidences"], "amber"),
        ("Total evenements", stats["total_alerts"], "slate"),
    ]
    items = "".join(
        f"""
        <div class="score-card score-{color}">
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
        """
        for label, value, color in cards
    )
    return f'<div class="score-grid">{items}</div>'


def alerts_to_dataframe(alerts: list[dict]) -> pd.DataFrame:
    if not alerts:
        return pd.DataFrame(columns=["id", "date", "niveau", "message", "classes", "statut"])
    return pd.DataFrame(
        [
            {
                "id": alert["id"],
                "date": str(alert["timestamp"])[:19].replace("T", " "),
                "niveau": alert["niveau"],
                "message": alert["message"],
                "classes": alert.get("classes") or "",
                "statut": alert["status"],
            }
            for alert in alerts
        ]
    )


def load_recent_alerts() -> pd.DataFrame:
    return alerts_to_dataframe(get_alerts(limit=8))


def alert_level_class(niveau: str) -> str:
    return {
        "URGENCE": "row-urgent",
        "CRITIQUE": "row-critical",
        "ELEVE": "row-high",
        "MODERE": "row-medium",
        "INFO": "row-info",
    }.get(niveau, "row-info")


def alerts_html(alerts: list[dict], limit: int | None = None) -> str:
    visible_alerts = alerts[:limit] if limit else alerts
    if not visible_alerts:
        return '<div class="empty-state">Aucun evenement pour le moment.</div>'

    rows = []
    for alert in visible_alerts:
        niveau = alert.get("niveau", "INFO")
        row_class = alert_level_class(niveau)
        date = str(alert.get("timestamp", ""))[:19].replace("T", " ")
        message = alert.get("message", "")
        classes = alert.get("classes") or "Aucune"
        status = alert.get("status", "")
        rows.append(
            f"""
            <tr class="{row_class}">
                <td><strong>{niveau}</strong></td>
                <td>{date}</td>
                <td>{message}</td>
                <td>{classes}</td>
                <td><span class="status-pill">{status}</span></td>
            </tr>
            """
        )

    return f"""
    <table class="ops-table">
        <thead>
            <tr>
                <th>Niveau</th>
                <th>Date</th>
                <th>Evenement</th>
                <th>Classes</th>
                <th>Statut</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    """


def recent_alerts_html() -> str:
    return alerts_html(get_alerts(limit=3))


def filter_alerts_html(niveau: str, status: str, date_value) -> str:
    return alerts_html(get_alerts(niveau=niveau, status=status, date_value=date_value))


def filter_alerts(niveau: str, status: str, date_value) -> pd.DataFrame:
    return alerts_to_dataframe(get_alerts(niveau=niveau, status=status, date_value=date_value))


def change_alert_status(alert_id, status: str) -> tuple[str, pd.DataFrame]:
    if not alert_id:
        return "Selectionnez un identifiant d'alerte.", load_recent_alerts()
    try:
        update_alert_status(int(alert_id), status)
    except Exception as exc:
        return f"Erreur : {exc}", load_recent_alerts()
    return "Statut mis a jour.", load_recent_alerts()


def change_alert_status_html(alert_id, status: str) -> tuple[str, str]:
    if not alert_id:
        return "Selectionnez un identifiant d'alerte.", recent_alerts_html()
    try:
        update_alert_status(int(alert_id), status)
    except Exception as exc:
        return f"Erreur : {exc}", recent_alerts_html()
    return "Statut mis a jour.", recent_alerts_html()


def build_daily_chart():
    alerts = get_alerts()
    if not alerts:
        return px.bar(title="Aucune alerte enregistree")

    df = pd.DataFrame(alerts)
    parsed_ts = pd.to_datetime(df["timestamp"], format="ISO8601", errors="coerce")
    df = df[parsed_ts.notna()].copy()
    if df.empty:
        return px.bar(title="Aucune alerte exploitable")
    df["date"] = parsed_ts[parsed_ts.notna()].dt.date
    daily = df.groupby(["date", "niveau"]).size().reset_index(name="nombre")
    fig = px.bar(daily, x="date", y="nombre", color="niveau", title="Alertes par jour", barmode="group")
    fig.update_layout(template="plotly_dark", height=260, margin=dict(l=12, r=12, t=42, b=12))
    return fig


def build_level_chart():
    alerts = get_alerts()
    if not alerts:
        return px.pie(title="Aucune alerte enregistree")

    df = pd.DataFrame(alerts)
    fig = px.pie(df, names="niveau", title="Repartition")
    fig.update_layout(template="plotly_dark", height=260, margin=dict(l=12, r=12, t=42, b=12))
    return fig


def list_photos() -> list[str]:
    return [str(path.resolve()) for path in list_evidence_files("photos")[:12]]


def list_videos() -> pd.DataFrame:
    videos = list_evidence_files("videos")
    rows = [
        {
            "fichier": path.name,
            "niveau": path.parent.parent.name,
            "groupe": path.parent.name,
            "action": "Disponible dans la bibliotheque video",
        }
        for path in videos
    ]
    return pd.DataFrame(rows, columns=["fichier", "niveau", "groupe", "action"])


def grouped_evidence_dataframe() -> pd.DataFrame:
    rows = evidence_groups("photos") + evidence_groups("videos")
    if not rows:
        return pd.DataFrame(columns=["niveau", "groupe", "nombre", "dernier_fichier"])
    cleaned = []
    for row in rows:
        item = dict(row)
        item["dernier_fichier"] = Path(item.get("dernier_fichier", "")).name
        cleaned.append(item)
    return pd.DataFrame(cleaned)


def prepare_video_for_gradio(path: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path

    fixed_path = path.with_name(f"{path.stem}_compatible.mp4")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(fixed_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return fixed_path
    except Exception:
        return path


def analyse_image_file(path: Path, threshold: float, save_evidence: bool):
    image = cv2.imread(str(path))
    if image is None:
        return None, None, "Impossible de lire cette image."

    detector = get_detector(threshold=float(threshold))
    boxes, scores, class_ids = detector.detect(image)
    annotated = detector.draw_results(image, boxes, scores, class_ids)
    unique_classes = sorted(set(class_ids))
    alerte = get_alerte(unique_classes)
    class_names = get_class_names(unique_classes)

    photo_path = None
    if save_evidence and alerte["priorite"] >= 2:
        photo_path = save_photo(annotated, niveau=alerte["niveau"])
        save_alert(alerte, class_names, photo_path=photo_path)

    status = [
        "Analyse image terminee.",
        f"Niveau : {alerte['niveau']}",
        f"Message : {alerte['message']}",
        f"Detections : {', '.join(class_names) if class_names else 'Aucune'}",
        f"Preuve : {photo_path if photo_path else 'non sauvegardee'}",
    ]
    return bgr_to_rgb(annotated), None, "\n".join(status)


def analyse_video_file(path: Path, threshold: float, save_evidence: bool):
    detector = get_detector(threshold=float(threshold))
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        yield None, None, "Impossible d'ouvrir cette video."
        return

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = VIDEOS_DIR / "analyses"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"analyse_{make_timestamp()}.mp4"

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    frame_count = 0
    alert_count = 0
    alert_frames = []
    saved_signatures = set()
    last_preview = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        boxes, scores, class_ids = detector.detect(frame)
        annotated = detector.draw_results(frame, boxes, scores, class_ids)
        writer.write(annotated)

        unique_classes = sorted(set(class_ids))
        alerte = get_alerte(unique_classes)
        if alerte["priorite"] >= 2:
            alert_count += 1
            alert_frames.append(annotated)
            signature = tuple(unique_classes)
            if save_evidence and signature not in saved_signatures:
                class_names = get_class_names(unique_classes)
                photo_path = save_photo(annotated, niveau=alerte["niveau"])
                clip_path = save_video_clip(alert_frames[-20:], fps=min(fps, 20), niveau=alerte["niveau"])
                save_alert(alerte, class_names, photo_path=photo_path, video_path=clip_path)
                saved_signatures.add(signature)

        if frame_count == 1 or frame_count % 12 == 0:
            progress = f"{frame_count}/{total_frames}" if total_frames else str(frame_count)
            last_preview = bgr_to_rgb(annotated)
            yield last_preview, None, f"Analyse en cours... frame {progress} | alertes : {alert_count}"

    cap.release()
    writer.release()
    output_path = prepare_video_for_gradio(output_path)
    summary = f"Analyse video terminee. Frames traitees : {frame_count}. Alertes detectees : {alert_count}."
    yield last_preview, str(output_path.resolve()), summary


def source_to_capture(source_mode: str, webcam_index, rtsp_url: str, video_file):
    if source_mode == "Webcam":
        return int(webcam_index or 0), None
    if source_mode == "RTSP":
        return rtsp_url, None
    path = file_path(video_file)
    return str(path) if path else None, path


def surveillance_live(
    source_mode: str,
    webcam_index,
    rtsp_url: str,
    video_file,
    threshold: float,
    save_evidence: bool,
    max_frames: int,
):
    source, _ = source_to_capture(source_mode, webcam_index, rtsp_url, video_file)
    if source is None or source == "":
        yield None, "Choisissez une source video.", recent_alerts_html(), grouped_evidence_dataframe()
        return

    try:
        detector = get_detector(threshold=float(threshold))
    except ModelNotAvailableError as exc:
        yield None, str(exc), recent_alerts_html(), grouped_evidence_dataframe()
        return

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        yield None, "Impossible d'ouvrir la source video.", recent_alerts_html(), grouped_evidence_dataframe()
        return

    frame_count = 0
    alert_count = 0
    alert_frames = []
    saved_signatures = set()
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    limit = int(max_frames or 600)

    while frame_count < limit:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        boxes, scores, class_ids = detector.detect(frame)
        annotated = detector.draw_results(frame, boxes, scores, class_ids)
        unique_classes = sorted(set(class_ids))
        alerte = get_alerte(unique_classes)

        if alerte["priorite"] >= 2:
            alert_count += 1
            alert_frames.append(annotated)
            signature = tuple(unique_classes)
            if save_evidence and signature not in saved_signatures:
                class_names = get_class_names(unique_classes)
                photo_path = save_photo(annotated, niveau=alerte["niveau"])
                clip_path = save_video_clip(alert_frames[-20:], fps=min(fps, 20), niveau=alerte["niveau"])
                save_alert(alerte, class_names, photo_path=photo_path, video_path=clip_path)
                saved_signatures.add(signature)

        class_names = get_class_names(unique_classes)
        status = (
            f"Surveillance active | frame {frame_count} | alertes {alert_count}\n"
            f"Niveau courant : {alerte['niveau']}\n"
            f"Detections : {', '.join(class_names) if class_names else 'Aucune'}"
        )
        yield bgr_to_rgb(annotated), status, recent_alerts_html(), grouped_evidence_dataframe()

    cap.release()
    yield None, f"Surveillance terminee. Frames traitees : {frame_count}. Alertes : {alert_count}.", recent_alerts_html(), grouped_evidence_dataframe()


def analyse_media(file_value, threshold: float, save_evidence: bool):
    path = file_path(file_value)
    if not path:
        yield None, None, "Deposez une image ou une video.", recent_alerts_html(), grouped_evidence_dataframe(), list_photos()
        return

    suffix = path.suffix.lower()
    try:
        if suffix in IMAGE_EXTENSIONS:
            image, video, status = analyse_image_file(path, threshold, save_evidence)
            yield image, video, status, recent_alerts_html(), grouped_evidence_dataframe(), list_photos()
            return

        if suffix in VIDEO_EXTENSIONS:
            for image, video, status in analyse_video_file(path, threshold, save_evidence):
                yield image, video, status, recent_alerts_html(), grouped_evidence_dataframe(), list_photos()
            return

        yield None, None, "Format non supporte. Utilisez une image ou une video.", recent_alerts_html(), grouped_evidence_dataframe(), list_photos()
    except ModelNotAvailableError as exc:
        yield None, None, str(exc), recent_alerts_html(), grouped_evidence_dataframe(), list_photos()
    except Exception as exc:
        yield None, None, f"Erreur pendant l'analyse : {exc}", recent_alerts_html(), grouped_evidence_dataframe(), list_photos()


def create_superviseur_tab():
    with gr.Tab("Superviseur"):
        kpi_cards = gr.HTML(score_cards_html())

        with gr.Tabs():
            with gr.Tab("Direct"):
                gr.Markdown("### Surveillance en temps reel")
                with gr.Row():
                    with gr.Column(scale=4, min_width=30, elem_classes="control-panel half-panel"):
                        source_mode = gr.Radio(["Webcam", "RTSP", "Fichier video"], value="Webcam", label="Source")
                        webcam_index = gr.Number(value=0, precision=0, label="Index webcam")
                        rtsp_url = gr.Textbox(label="URL RTSP", placeholder="rtsp://adresse:port/stream")
                        live_video_file = gr.File(
                            label="Flux video de test",
                            file_types=[".mp4", ".avi", ".mov", ".mkv", ".webm"],
                        )
                        live_threshold = gr.Slider(0.1, 0.95, value=0.5, step=0.05, label="Seuil")
                        live_save = gr.Checkbox(value=True, label="Sauvegarder alertes critiques")
                        max_frames = gr.Slider(60, 3000, value=600, step=60, label="Limite frames")
                        live_btn = gr.Button("Demarrer", variant="primary")
                        live_status = gr.Textbox(label="Etat", lines=2)
                    with gr.Column(scale=4):
                        live_stream = gr.Image(label="Flux annote", height=430, streaming=True)

                gr.Markdown("### Alertes rapides")
                recent_alerts = gr.HTML(recent_alerts_html())

            with gr.Tab("Analyse ponctuelle"):
                gr.Markdown("### Traitement d'un fichier (image ou video)")
                with gr.Row():
                    with gr.Column(scale=1, min_width=120, elem_classes="control-panel half-panel"):
                        media_input = gr.File(
                            label="Image ou video",
                            file_types=[".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".avi", ".mov", ".mkv", ".webm"],
                        )
                        threshold = gr.Slider(0.1, 0.95, value=0.5, step=0.05, label="Seuil")
                        save_evidence = gr.Checkbox(value=True, label="Sauvegarder preuves critiques")
                        analyse_btn = gr.Button("Analyser", variant="secondary")
                        analyse_text = gr.Textbox(label="Etat", lines=2)
                    with gr.Column(scale=4):
                        live_preview = gr.Image(label="Resultat annote", height=330)
                        annotated_video = gr.Video(label="Video annotee", interactive=False)

            with gr.Tab("Journal"):
                with gr.Row():
                    niveau_filter = gr.Dropdown(["Tous", "URGENCE", "CRITIQUE", "ELEVE", "MODERE", "INFO"], value="Tous", label="Niveau")
                    status_filter = gr.Dropdown(["Tous", "non_lu", "lu", "traite"], value="Tous", label="Statut")
                    date_filter = gr.Textbox(label="Date", placeholder="2026-05-13")
                    filter_btn = gr.Button("Filtrer", size="sm")
                filtered_alerts = gr.HTML(alerts_html(get_alerts()))

                with gr.Row():
                    alert_id = gr.Number(label="ID technique", precision=0)
                    new_status = gr.Dropdown(["non_lu", "lu", "traite"], value="lu", label="Nouveau statut")
                    update_status_btn = gr.Button("Mettre a jour", size="sm")
                status_message = gr.Textbox(label="Message", interactive=False)

                with gr.Accordion("Statistiques", open=False):
                    with gr.Row():
                        daily_plot = gr.Plot(label="Evolution")
                        level_plot = gr.Plot(label="Repartition")

            with gr.Tab("Preuves"):
                refresh_evidence = gr.Button("Actualiser la bibliotheque", size="sm")
                with gr.Row():
                    with gr.Column(scale=2):
                        gallery = gr.Gallery(label="Galerie de Preuves", columns=4, height=360)
                    with gr.Column(scale=1):
                        evidence_groups_table = gr.Dataframe(label="Groupes similaires", interactive=False)
                video_files = gr.Dataframe(label="Bibliotheque Video", interactive=False)

        refresh_outputs = [
            kpi_cards,
            recent_alerts,
            daily_plot,
            level_plot,
            gallery,
            video_files,
            evidence_groups_table,
        ]

        def refresh_all():
            return (
                score_cards_html(),
                recent_alerts_html(),
                build_daily_chart(),
                build_level_chart(),
                list_photos(),
                list_videos(),
                grouped_evidence_dataframe(),
            )

        live_btn.click(
            surveillance_live,
            inputs=[source_mode, webcam_index, rtsp_url, live_video_file, live_threshold, live_save, max_frames],
            outputs=[live_stream, live_status, recent_alerts, evidence_groups_table],
        )
        analyse_btn.click(
            analyse_media,
            inputs=[media_input, threshold, save_evidence],
            outputs=[live_preview, annotated_video, analyse_text, recent_alerts, evidence_groups_table, gallery],
        )
        filter_btn.click(filter_alerts_html, inputs=[niveau_filter, status_filter, date_filter], outputs=filtered_alerts)
        update_status_btn.click(change_alert_status_html, inputs=[alert_id, new_status], outputs=[status_message, recent_alerts])
        refresh_evidence.click(
            lambda: (list_photos(), list_videos(), grouped_evidence_dataframe()),
            outputs=[gallery, video_files, evidence_groups_table],
        )

        return refresh_all, refresh_outputs
