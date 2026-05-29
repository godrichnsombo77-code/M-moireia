from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "best (2)_openvino_model.xml"


class ModelNotAvailableError(RuntimeError):
    pass


class OpenVINODetector:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH, threshold: float = 0.5):
        try:
            from openvino import Core
        except Exception as exc:
            raise ModelNotAvailableError("OpenVINO n'est pas installe.") from exc

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise ModelNotAvailableError(f"Modele introuvable : {self.model_path}")

        self.core = Core()
        self.model = self.core.read_model(str(self.model_path))
        self.compiled_model = self.core.compile_model(self.model, "CPU")
        self.input_layer = self.compiled_model.input(0)
        self.output_layer = self.compiled_model.output(0)
        self.input_shape = self.input_layer.shape
        self.height = int(self.input_shape[2])
        self.width = int(self.input_shape[3])
        self.threshold = float(threshold)
        self.nms_threshold = 0.4
        self.classes = {
            0: "Non-Violence",
            1: "Violence",
            2: "Arme a feu",
            3: "Couteau",
            4: "Personne",
        }

    def preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, int, int]:
        original_h, original_w = frame.shape[:2]
        gain = min(self.width / original_w, self.height / original_h)
        resized_w = max(1, int(round(original_w * gain)))
        resized_h = max(1, int(round(original_h * gain)))
        resized = cv2.resize(frame, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        pad_w = self.width - resized_w
        pad_h = self.height - resized_h
        pad_left = pad_w // 2
        pad_right = pad_w - pad_left
        pad_top = pad_h // 2
        pad_bottom = pad_h - pad_top
        letterboxed = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )
        rgb = cv2.cvtColor(letterboxed, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0
        input_data = np.expand_dims(np.transpose(normalized, (2, 0, 1)), axis=0)
        return input_data, original_w, original_h, gain, pad_left, pad_top

    def detect(self, frame: np.ndarray) -> tuple[list[list[int]], list[float], list[int]]:
        input_data, original_w, original_h, gain, pad_left, pad_top = self.preprocess(frame)
        result = self.compiled_model([input_data])[self.output_layer]
        detections = np.squeeze(result)

        boxes_xyxy = []
        boxes_xywh = []
        scores = []
        class_ids = []

        for detection in detections:
            if len(detection) < 6:
                continue
            x1, y1, x2, y2, confidence, class_id = detection[:6]
            if float(confidence) < self.threshold:
                continue

            x1 = float(x1)
            y1 = float(y1)
            x2 = float(x2)
            y2 = float(y2)
            if max(x1, y1, x2, y2) <= 1.5:
                x1 *= self.width
                y1 *= self.height
                x2 *= self.width
                y2 *= self.height

            x1 = (x1 - pad_left) / gain
            y1 = (y1 - pad_top) / gain
            x2 = (x2 - pad_left) / gain
            y2 = (y2 - pad_top) / gain

            x1_abs = max(0, min(int(round(x1)), original_w - 1))
            y1_abs = max(0, min(int(round(y1)), original_h - 1))
            x2_abs = max(0, min(int(round(x2)), original_w - 1))
            y2_abs = max(0, min(int(round(y2)), original_h - 1))
            width = max(1, x2_abs - x1_abs)
            height = max(1, y2_abs - y1_abs)

            boxes_xyxy.append([x1_abs, y1_abs, x2_abs, y2_abs])
            boxes_xywh.append([x1_abs, y1_abs, width, height])
            scores.append(float(confidence))
            class_ids.append(int(class_id))

        if not boxes_xywh:
            return [], [], []

        indices = cv2.dnn.NMSBoxes(boxes_xywh, scores, self.threshold, self.nms_threshold)
        if len(indices) == 0:
            return [], [], []

        flat_indices = np.array(indices).flatten().tolist()
        return (
            [boxes_xyxy[i] for i in flat_indices],
            [scores[i] for i in flat_indices],
            [class_ids[i] for i in flat_indices],
        )

    def draw_results(
        self,
        frame: np.ndarray,
        boxes: list[list[int]],
        scores: list[float],
        class_ids: list[int],
    ) -> np.ndarray:
        image = frame.copy()
        for box, score, class_id in zip(boxes, scores, class_ids):
            x1, y1, x2, y2 = box
            class_name = self.classes.get(class_id, f"Classe {class_id}")
            color = self._color_for_class(class_id)
            label = f"{class_name} {score * 100:.1f}%"

            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            text_w, text_h = text_size
            y_label = max(22, y1)
            cv2.rectangle(image, (x1, y_label - text_h - 8), (x1 + text_w + 8, y_label), color, -1)
            cv2.putText(
                image,
                label,
                (x1 + 4, y_label - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return image

    @staticmethod
    def _color_for_class(class_id: int) -> tuple[int, int, int]:
        if class_id == 1:
            return (36, 36, 220)
        if class_id in {2, 3}:
            return (0, 140, 255)
        if class_id == 4:
            return (48, 170, 80)
        return (210, 170, 30)


@lru_cache(maxsize=4)
def get_detector(model_path: str = str(DEFAULT_MODEL_PATH), threshold: float = 0.5) -> OpenVINODetector:
    return OpenVINODetector(model_path=model_path, threshold=threshold)


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
