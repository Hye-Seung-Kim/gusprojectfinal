"""
gus_mediapipe_projection.py

VIAM camera → MediaPipe segmentation → projector display.
Replaces rembg with MediaPipe for real-time, low-latency segmentation.

Controls:
  Q  — quit
  M  — move window to projector (fullscreen)
  [  — decrease edge softness
  ]  — increase edge softness
"""

import asyncio
import cv2
import numpy as np
import urllib.request
import os

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from viam_client import connect_robot, get_camera_handle
from utils import viam_image_to_cv2
from dog_detector import DogDetector

# ---------------------------------------------------------------------------
PROJECTOR_X = 1920
PROJECTOR_Y = 0
PROJECTOR_W = 1920
PROJECTOR_H = 1080
WINDOW_NAME = "Gus"
EDGE_BLUR   = 7
FADE_RATE   = 0.08
HOLD_FRAMES = 15
CONF_THRESH = 0.02
GAMMA       = 0.8
CONTRAST    = 1.5    # >1 = more contrast (try 1.3–2.0)
BRIGHTNESS  = 0.05   # 0–1 additive lift (try 0.0–0.15)
PAD         = 120

MODEL_PATH  = os.path.join(os.path.dirname(__file__), "selfie_segmenter_landscape.tflite")
MODEL_URL   = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite"
# ---------------------------------------------------------------------------


def download_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading selfie_segmenter_landscape.tflite...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Downloaded.")


def build_segmenter():
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.ImageSegmenterOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.IMAGE,
        output_confidence_masks=True
    )
    return mp_vision.ImageSegmenter.create_from_options(options)


def segment_frame(segmenter, detector, frame):
    """Detect Gus, then run MediaPipe only inside his bounding box."""
    h, w   = frame.shape[:2]
    boxes  = detector.detect(frame, conf=0.05)

    if not boxes:
        print("no detection", flush=True)
        return None  # Gus not found
    print(f"Gus detected: {len(boxes)} box(es)", flush=True)

    # Use largest box
    boxes.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]), reverse=True)
    x1, y1, x2, y2 = boxes[0]
    x1c = max(0, x1 - PAD);  y1c = max(0, y1 - PAD)
    x2c = min(w, x2 + PAD);  y2c = min(h, y2 + PAD)

    crop      = frame[y1c:y2c, x1c:x2c]
    rgb       = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    results   = segmenter.segment(mp_image)
    crop_mask = results.confidence_masks[0].numpy_view().copy()
    crop_mask = cv2.resize(crop_mask, (x2c - x1c, y2c - y1c), interpolation=cv2.INTER_CUBIC)

    full_mask = np.zeros((h, w), dtype=np.float32)
    full_mask[y1c:y2c, x1c:x2c] = crop_mask
    full_mask = cv2.GaussianBlur(full_mask, (0, 0), sigmaX=18)
    return full_mask


def process_mask(raw_mask, frame, edge_blur):
    """Guided filter + blur — mask is already at full frame resolution."""
    gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask   = cv2.ximgproc.guidedFilter(guide=gray, src=raw_mask, radius=16, eps=1e-3)
    blur_k = edge_blur | 1
    mask   = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)
    return np.nan_to_num(np.clip(mask, 0.0, 1.0), nan=0.0)


def make_canvas(frame, mask, cw, ch):
    h, w   = frame.shape[:2]
    scale  = min(cw / w, ch / h)
    nw, nh = int(w * scale), int(h * scale)
    ox, oy = (cw - nw) // 2, (ch - nh) // 2
    canvas = np.zeros((ch, cw, 3), dtype=np.uint8)

    if mask is not None:
        # Gamma lift + contrast boost for projector visibility
        lifted   = np.power(np.clip(frame.astype(np.float32) / 255.0, 0.0, 1.0), GAMMA)
        # Contrast: alpha>1 increases contrast, beta shifts brightness
        boosted  = np.clip(lifted * CONTRAST + BRIGHTNESS, 0.0, 1.0)
        frame_s  = cv2.resize((boosted * 255).astype(np.uint8), (nw, nh))
        mask_s   = cv2.resize(mask, (nw, nh))[:, :, np.newaxis]
        canvas[oy:oy+nh, ox:ox+nw] = (frame_s.astype(np.float32) * mask_s).astype(np.uint8)
    else:
        cv2.putText(canvas, "Waiting for Gus...", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return canvas


async def main():
    print("Starting...")
    download_model()
    print("Model ready.")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, PROJECTOR_W, PROJECTOR_H)

    status = np.zeros((PROJECTOR_H, PROJECTOR_W, 3), dtype=np.uint8)
    cv2.putText(status, "Connecting to VIAM...", (20, PROJECTOR_H // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    cv2.imshow(WINDOW_NAME, status)
    cv2.waitKey(1)

    try:
        robot = await asyncio.wait_for(connect_robot(), timeout=15)
    except Exception as e:
        print(f"Connection failed: {e}")
        cv2.destroyAllWindows()
        return

    print("Connected.")
    camera = await get_camera_handle(robot)
    print("Camera ready.  Q=quit  M=projector  [ / ]=edge softness")

    print("Loading Gus detector...")
    detector     = DogDetector()
    segmenter    = build_segmenter()
    print("Models ready.")
    smoothed        = None
    no_detect_count = 0
    edge_blur    = EDGE_BLUR
    canvas_w     = PROJECTOR_W
    canvas_h     = PROJECTOR_H

    try:
        while True:
            try:
                images, _ = await asyncio.wait_for(camera.get_images(), timeout=5)
            except Exception as e:
                print(f"Frame error: {e}")
                await asyncio.sleep(0.5)
                continue

            if not images:
                await asyncio.sleep(0.1)
                continue

            frame = viam_image_to_cv2(images[0])
            if frame is None:
                continue

            # Detect + segment (non-blocking)
            raw_mask      = await asyncio.to_thread(segment_frame, segmenter, detector, frame)

            if raw_mask is None or raw_mask.max() < CONF_THRESH or raw_mask.mean() < 0.06:
                no_detect_count += 1
                if smoothed is not None and no_detect_count > HOLD_FRAMES:
                    smoothed = np.clip(smoothed - FADE_RATE, 0, 1)
                    if smoothed.max() < 0.01:
                        smoothed = None
            else:
                no_detect_count = 0
                mask     = process_mask(raw_mask, frame, edge_blur)
                smoothed = mask.copy() if smoothed is None else \
                           0.3 * smoothed + 0.7 * mask

            canvas = make_canvas(frame, smoothed, canvas_w, canvas_h)
            cv2.imshow(WINDOW_NAME, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("m"):
                cv2.moveWindow(WINDOW_NAME, PROJECTOR_X, PROJECTOR_Y)
                cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
                                      cv2.WINDOW_FULLSCREEN)
                canvas_w = PROJECTOR_W
                canvas_h = PROJECTOR_H
                print(f"Moved to projector ({PROJECTOR_W}x{PROJECTOR_H})")
            elif key == ord("["):
                edge_blur = max(1, edge_blur - 2)
                print(f"Edge blur: {edge_blur}")
            elif key == ord("]"):
                edge_blur = min(41, edge_blur + 2)
                print(f"Edge blur: {edge_blur}")

    finally:
        segmenter.close()
        cv2.destroyAllWindows()
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
