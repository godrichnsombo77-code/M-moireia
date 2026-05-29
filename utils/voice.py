import json
import os
import subprocess
import shutil
from functools import lru_cache
from pathlib import Path

import wave

from gtts import gTTS
from vosk import KaldiRecognizer, Model


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VOSK_MODEL = BASE_DIR / "vosk-model-small-fr-0.22"
DEFAULT_FFMPEG = os.getenv("FFMPEG_PATH", "ffmpeg")
KNOWN_FFMPEG = Path(r"C:\Users\HP\Downloads\ffmpeg-2025-08-20-git-4d7c609be3-full_build\bin\ffmpeg.exe")
AUDIO_DIR = BASE_DIR / "evidences" / "audio"


def _resolve_ffmpeg() -> str:
    candidate = os.getenv("FFMPEG_PATH", "").strip()
    if candidate:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return str(candidate_path)
        return candidate
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    if KNOWN_FFMPEG.exists():
        return str(KNOWN_FFMPEG)
    return "ffmpeg"


@lru_cache(maxsize=1)
def get_vosk_model() -> Model:
    model_path = Path(os.getenv("VOSK_MODEL_PATH", str(DEFAULT_VOSK_MODEL))).expanduser()
    if not model_path.exists():
        raise FileNotFoundError(f"Modele Vosk introuvable: {model_path}")
    return Model(str(model_path))


def _convert_to_wav(input_path: Path) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_DIR / f"{input_path.stem}.wav"
    ffmpeg = _resolve_ffmpeg()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        "-f",
        "wav",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "Conversion audio impossible avec ffmpeg. "
            f"Sortie: {result.stderr.strip() or result.stdout.strip()}"
        )
    return output_path


def transcribe_audio_file(file_path: str | Path) -> str:
    source_path = Path(file_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Fichier audio introuvable: {source_path}")

    wav_path = source_path
    if source_path.suffix.lower() != ".wav":
        wav_path = _convert_to_wav(source_path)

    model = get_vosk_model()
    with wave.open(str(wav_path), "rb") as wf:
        recognizer = KaldiRecognizer(model, wf.getframerate())
        recognizer.SetWords(True)
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            recognizer.AcceptWaveform(data)
        result = json.loads(recognizer.FinalResult())
    return result.get("text", "").strip()


def text_to_speech_file(text: str, prefix: str = "qwen") -> Path | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_DIR / f"{prefix}_{os.urandom(6).hex()}.mp3"
    gTTS(cleaned, lang="fr").save(str(output_path))
    return output_path
