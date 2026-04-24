"""
dog_detector.py

YOLOv8 dog detection using onnxruntime — no torch required.
Returns bounding boxes for detected dogs only (COCO class 16).
"""

import cv2
import numpy as np
import onnxruntime as ort
import urllib.request
import os

MODEL_PATH  = os.path.join(os.path.dirname(__file__), "yolov8n.onnx")
MODEL_URL   = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx"
COCO_DOG    = 16
INPUT_SIZE  = 640


def download_model():
    if os.path.exists(MODEL_PATH):
        return
    print(f"Downloading yolov8n.onnx (~12MB)...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Downloaded.")


def _preprocess(frame):
    """Resize and normalize frame to 640x640 float32."""
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (INPUT_SIZE, INPUT_SIZE))
    img = img.astype(np.float32) / 255.0
    return img.transpose(2, 0, 1)[np.newaxis]   # [1, 3, 640, 640]


def _postprocess(output, orig_h, orig_w, conf=0.4):
    """
    output: [1, 84, 8400]
    Returns list of (x1, y1, x2, y2) in original image coords.
    """
    preds = output[0].T                          # [8400, 84]
    boxes_raw  = preds[:, :4]                    # cx, cy, w, h (normalised to 640)
    scores_all = preds[:, 4:]                    # [8400, 80]

    class_ids  = scores_all.argmax(axis=1)
    class_conf = scores_all.max(axis=1)

    dog_mask = (class_ids == COCO_DOG) & (class_conf > conf)
    if not dog_mask.any():
        return []

    boxes  = boxes_raw[dog_mask]
    scores = class_conf[dog_mask]

    # cx,cy,w,h → x1,y1,x2,y2 (still in 640-space)
    x1 = boxes[:, 0] - boxes[:, 2] / 2
    y1 = boxes[:, 1] - boxes[:, 3] / 2
    x2 = boxes[:, 0] + boxes[:, 2] / 2
    y2 = boxes[:, 1] + boxes[:, 3] / 2

    # Scale to original size
    sx, sy = orig_w / INPUT_SIZE, orig_h / INPUT_SIZE
    x1, x2 = (x1 * sx).astype(int), (x2 * sx).astype(int)
    y1, y2 = (y1 * sy).astype(int), (y2 * sy).astype(int)

    # NMS
    rects  = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
    idxs   = cv2.dnn.NMSBoxes(rects, scores.tolist(), conf, 0.45)
    if len(idxs) == 0:
        return []

    idxs = idxs.flatten()
    return [(x1[i], y1[i], x2[i], y2[i]) for i in idxs]


class DogDetector:
    def __init__(self):
        download_model()
        self.session = ort.InferenceSession(
            MODEL_PATH,
            providers=["CoreMLExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def detect(self, frame, conf=0.4):
        """Returns list of (x1, y1, x2, y2) bounding boxes for dogs."""
        h, w = frame.shape[:2]
        inp    = _preprocess(frame)
        output = self.session.run(None, {self.input_name: inp})
        return _postprocess(output[0], h, w, conf)
