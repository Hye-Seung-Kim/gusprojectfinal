"""
gus_webcam_test.py

Reads webcam, removes background using rembg (no torch required),
and displays Gus as a floating cutout on black background — fullscreen on projector.

Controls:
  Q     — quit
  F     — toggle fullscreen
  M     — move window to projector display
  +/-   — scale Gus up/down
  arrows — nudge Gus position
  [ / ] — decrease / increase edge softness
  ; / ' — decrease / increase temporal smoothing
"""

import cv2
import numpy as np
import threading
from rembg import new_session, remove as rembg_remove
from dog_detector import DogDetector

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CAMERA_INDEX    = 1
SEG_MODEL       = "u2netp"    # fastest; "u2net" for better quality
INFER_SIZE      = 320         # resize frame before segmentation (smaller = faster)
PROJECTOR_X     = 1920
PROJECTOR_Y     = 0
WINDOW_NAME     = "gus"

# Smoothing — tune live with [ ] and ; '
EDGE_BLUR       = 21          # feather mask edges (higher = softer)
TEMPORAL_SMOOTH = 0.6         # 0=snap to new mask, 0.95=very slow/smooth
MORPH_KERNEL    = 7           # fills holes and removes noise in mask
# ---------------------------------------------------------------------------

_lock         = threading.Lock()
_latest_frame = None
_latest_mask  = None          # float32 [0,1], temporally smoothed
_smooth_params = [EDGE_BLUR, TEMPORAL_SMOOTH]
_model_ready  = False


def segmentation_worker():
    global _latest_mask, _model_ready

    print("Loading models...")
    detector = DogDetector()
    seg_session = new_session(SEG_MODEL)
    _model_ready = True
    print("Models ready.")

    smoothed = None
    morph_k  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL, MORPH_KERNEL))
    PAD      = 40   # pixels to pad around dog bbox before rembg

    while True:
        with _lock:
            frame = _latest_frame.copy() if _latest_frame is not None else None
            edge_blur, temporal = _smooth_params

        if frame is None:
            continue

        h, w = frame.shape[:2]
        raw = np.zeros((h, w), dtype=np.float32)

        boxes = detector.detect(frame)
        if boxes:
            # Use the largest detected dog box
            boxes.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]), reverse=True)
            x1, y1, x2, y2 = boxes[0]

            # Pad and clamp
            x1c = max(0, x1 - PAD);  y1c = max(0, y1 - PAD)
            x2c = min(w, x2 + PAD);  y2c = min(h, y2 + PAD)

            crop = frame[y1c:y2c, x1c:x2c]
            rgba = rembg_remove(crop, session=seg_session)
            alpha = rgba[:, :, 3].astype(np.float32) / 255.0

            # Paste alpha back into full-size mask
            raw[y1c:y2c, x1c:x2c] = alpha

        # Clean up: fill holes, remove noise
        raw_u8 = (raw * 255).astype(np.uint8)
        raw_u8 = cv2.morphologyEx(raw_u8, cv2.MORPH_CLOSE, morph_k)
        raw_u8 = cv2.morphologyEx(raw_u8, cv2.MORPH_OPEN,  morph_k)
        raw    = raw_u8.astype(np.float32) / 255.0

        # Feather edges
        blur_k = edge_blur | 1
        raw = cv2.GaussianBlur(raw, (blur_k, blur_k), 0)

        # Temporal smoothing
        if smoothed is None or smoothed.shape != raw.shape:
            smoothed = raw.copy()
        else:
            smoothed = temporal * smoothed + (1.0 - temporal) * raw

        with _lock:
            _latest_mask = smoothed.copy()


def apply_mask(frame, mask, scale=1.0, offset_x=0, offset_y=0, canvas_size=None):
    """Composite Gus on a black canvas using float32 mask [0,1]."""
    h, w  = frame.shape[:2]
    alpha = cv2.resize(mask, (w, h))[:, :, np.newaxis]
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

    sx1 = max(0, -x);      dx1 = max(0, x)
    sy1 = max(0, -y);      dy1 = max(0, y)
    sx2 = min(new_w, cw - x);  dx2 = min(cw, x + new_w)
    sy2 = min(new_h, ch - y);  dy2 = min(ch, y + new_h)

    if sx2 > sx1 and sy2 > sy1:
        roi     = canvas[dy1:dy2, dx1:dx2].astype(np.float32)
        gus_roi = gus_scaled[sy1:sy2, sx1:sx2].astype(np.float32)
        a_roi   = mask_scaled[sy1:sy2, sx1:sx2]
        canvas[dy1:dy2, dx1:dx2] = (gus_roi * a_roi + roi * (1 - a_roi)).astype(np.uint8)

    return canvas


def main():
    global _latest_frame

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Could not open camera {CAMERA_INDEX}")
        return

    threading.Thread(target=segmentation_worker, daemon=True).start()
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    fullscreen = False
    scale      = 1.0
    offset_x   = 0
    offset_y   = 0
    canvas_size = None

    print("Ready. Q=quit  F=fullscreen  M=projector  +/-=scale  arrows=nudge")
    print("       [ / ] = edge softness    ; / ' = temporal smoothing")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed.")
            break

        with _lock:
            _latest_frame = frame.copy()
            mask = _latest_mask.copy() if _latest_mask is not None else None
            cur_blur, cur_temporal = _smooth_params

        try:
            _, _, ww, wh = cv2.getWindowImageRect(WINDOW_NAME)
            if ww > 0 and wh > 0:
                canvas_size = (ww, wh)
        except Exception:
            pass

        if mask is not None:
            display = apply_mask(frame, mask, scale, offset_x, offset_y, canvas_size)
        else:
            display = frame.copy()
            cv2.putText(display, "Loading model...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

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
            new_blur = max(1, cur_blur - 4)
            with _lock: _smooth_params[0] = new_blur
            print(f"Edge blur: {new_blur}")
        elif key == ord(']'):
            new_blur = min(81, cur_blur + 4)
            with _lock: _smooth_params[0] = new_blur
            print(f"Edge blur: {new_blur}")
        elif key == ord(';'):
            new_t = max(0.0, round(cur_temporal - 0.05, 2))
            with _lock: _smooth_params[1] = new_t
            print(f"Temporal smooth: {new_t}")
        elif key == ord("'"):
            new_t = min(0.95, round(cur_temporal + 0.05, 2))
            with _lock: _smooth_params[1] = new_t
            print(f"Temporal smooth: {new_t}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
