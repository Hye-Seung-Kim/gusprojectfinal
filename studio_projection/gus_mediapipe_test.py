"""
gus_mediapipe_test.py

Webcam test using MediaPipe SelfieSegmentation instead of rembg.
Runs segmentation inline (no worker thread) to test if latency is eliminated.
Prints FPS to terminal so you can compare with rembg version.

Install:
  pip install mediapipe
  (if Python 3.13 fails: create a 3.11 venv and pip install mediapipe opencv-python numpy)

Controls:
  Q         — quit
  F         — toggle fullscreen
  M         — move to projector
  +/-       — scale up/down
  arrows    — nudge position
  [ / ]     — edge softness
  0 / 1     — switch MediaPipe model (0=general, 1=landscape/better for non-portrait)
"""

import cv2
import numpy as np
import time

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
except ImportError:
    print("MediaPipe not installed. Run: pip install mediapipe")
    exit(1)

import urllib.request
import os
from dog_detector import DogDetector

# ---------------------------------------------------------------------------
CAMERA_INDEX = 0
PROJECTOR_X  = 1920
PROJECTOR_Y  = 0
WINDOW_NAME  = "gus-mediapipe"
EDGE_BLUR    = 7
CONF_THRESH  = 0.02
FADE_RATE    = 0.08
HOLD_FRAMES  = 15
GAMMA        = 0.8
PAD          = 120

MODEL_PATH = os.path.join(os.path.dirname(__file__), "selfie_segmenter_landscape.tflite")
MODEL_URL  = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite"
# ---------------------------------------------------------------------------


def download_model():
    if not os.path.exists(MODEL_PATH):
        print("Downloading selfie_segmenter_landscape.tflite (~1MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("Downloaded.")


def apply_mask(frame, mask, scale=1.0, offset_x=0, offset_y=0, canvas_size=None):
    h, w  = frame.shape[:2]
    alpha = mask[:, :, np.newaxis]
    gus   = (frame.astype(np.float32) * alpha).astype(np.uint8)

    if canvas_size is None:
        return gus

    cw, ch  = canvas_size
    canvas  = np.zeros((ch, cw, 3), dtype=np.uint8)
    new_w   = int(w * scale)
    new_h   = int(h * scale)
    if new_w < 1 or new_h < 1:
        return canvas

    gus_scaled  = cv2.resize(gus,  (new_w, new_h))
    mask_scaled = cv2.resize(mask, (new_w, new_h))[:, :, np.newaxis]

    x = (cw - new_w) // 2 + offset_x
    y = (ch - new_h) // 2 + offset_y

    sx1 = max(0, -x);       dx1 = max(0, x)
    sy1 = max(0, -y);       dy1 = max(0, y)
    sx2 = min(new_w, cw-x); dx2 = min(cw, x+new_w)
    sy2 = min(new_h, ch-y); dy2 = min(ch, y+new_h)

    if sx2 > sx1 and sy2 > sy1:
        roi     = canvas[dy1:dy2, dx1:dx2].astype(np.float32)
        gus_roi = gus_scaled[sy1:sy2, sx1:sx2].astype(np.float32)
        a_roi   = mask_scaled[sy1:sy2, sx1:sx2]
        canvas[dy1:dy2, dx1:dx2] = (gus_roi * a_roi + roi * (1 - a_roi)).astype(np.uint8)

    return canvas


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # manual mode
    cap.set(cv2.CAP_PROP_EXPOSURE, -2)      # adjust this: -1 bright, -10 dark
    if not cap.isOpened():
        print(f"Could not open camera {CAMERA_INDEX}. Try changing CAMERA_INDEX.")
        return

    download_model()
    base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
    options = mp_vision.ImageSegmenterOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.IMAGE,
        output_confidence_masks=True
    )
    segmenter = mp_vision.ImageSegmenter.create_from_options(options)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    fullscreen  = False
    scale       = 1.0
    offset_x    = 0
    offset_y    = 0
    canvas_size = None
    edge_blur   = EDGE_BLUR

    fps_counter = 0
    fps_timer   = time.time()
    fps_display = 0.0

    print("Loading Gus detector...")
    detector        = DogDetector()
    smoothed        = None
    no_detect_count = 0
    print("Ready.")
    print("  Q=quit  F=fullscreen  M=projector  +/-=scale  arrows=nudge  [ / ]=edge softness")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed.")
            break

        h, w   = frame.shape[:2]
        boxes  = detector.detect(frame, conf=0.01)

        if boxes:
            no_detect_count = 0
            boxes.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]), reverse=True)
            x1, y1, x2, y2 = boxes[0]
            x1c = max(0, x1-PAD); y1c = max(0, y1-PAD)
            x2c = min(w, x2+PAD); y2c = min(h, y2+PAD)

            crop      = frame[y1c:y2c, x1c:x2c]
            rgb       = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results   = segmenter.segment(mp_image)
            crop_mask = results.confidence_masks[0].numpy_view().copy()
            crop_mask = cv2.resize(crop_mask, (x2c-x1c, y2c-y1c), interpolation=cv2.INTER_CUBIC)

            full_mask = np.zeros((h, w), dtype=np.float32)
            full_mask[y1c:y2c, x1c:x2c] = crop_mask
            full_mask = cv2.GaussianBlur(full_mask, (0, 0), sigmaX=18)

            if full_mask.max() >= CONF_THRESH and full_mask.mean() > 0.06:
                gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mask   = cv2.ximgproc.guidedFilter(guide=gray, src=full_mask, radius=16, eps=1e-3)
                blur_k = edge_blur | 1
                mask   = np.clip(cv2.GaussianBlur(mask, (blur_k, blur_k), 0), 0.0, 1.0)
                mask   = np.nan_to_num(mask, nan=0.0)
                smoothed = mask.copy() if smoothed is None else 0.3 * smoothed + 0.7 * mask
        else:
            no_detect_count += 1
            if smoothed is not None and no_detect_count > HOLD_FRAMES:
                smoothed = np.clip(smoothed - FADE_RATE, 0, 1)
                if smoothed.max() < 0.01:
                    smoothed = None

        # --- FPS ---
        fps_counter += 1
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            fps_display = fps_counter / elapsed
            fps_counter = 0
            fps_timer   = time.time()
            status = f"detected" if boxes else "no detection"
            print(f"FPS: {fps_display:.1f}  {status}")

        # --- Canvas size ---
        try:
            _, _, ww, wh = cv2.getWindowImageRect(WINDOW_NAME)
            if ww > 0 and wh > 0:
                canvas_size = (ww, wh)
        except Exception:
            pass

        if smoothed is not None:
            lifted  = np.power(np.clip(frame.astype(np.float32) / 255.0, 0.0, 1.0), GAMMA)
            alpha   = smoothed[:, :, np.newaxis]
            display = np.clip(lifted * alpha * 255, 0, 255).astype(np.uint8)
        else:
            display = np.zeros_like(frame)
            cv2.putText(display, "Waiting for Gus...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # FPS overlay (top-left, small)
        cv2.putText(display, f"{fps_display:.0f} fps",
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.imshow(WINDOW_NAME, display)
        key = cv2.waitKey(1) & 0xFF

        if   key == ord('q'):
            break
        elif key == ord('f'):
            fullscreen = not fullscreen
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL)
        elif key == ord('m'):
            cv2.moveWindow(WINDOW_NAME, PROJECTOR_X, PROJECTOR_Y)
            cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            fullscreen = True
        elif key == ord('+') or key == ord('='):
            scale = min(scale + 0.1, 3.0)
        elif key == ord('-'):
            scale = max(scale - 0.1, 0.1)
        elif key == 81:  offset_x -= 20
        elif key == 83:  offset_x += 20
        elif key == 82:  offset_y -= 20
        elif key == 84:  offset_y += 20
        elif key == ord('['):
            edge_blur = max(1, edge_blur - 2)
            print(f"Edge blur: {edge_blur}")
        elif key == ord(']'):
            edge_blur = min(41, edge_blur + 2)
            print(f"Edge blur: {edge_blur}")

    cap.release()
    segmenter.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
