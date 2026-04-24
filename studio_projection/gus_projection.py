import asyncio
import threading
import cv2
import numpy as np
from rembg import new_session, remove as rembg_remove
from dog_detector import DogDetector
from viam_client import connect_robot, get_camera_handle
from utils import viam_image_to_cv2

# ---------------------------------------------------------------------------
# Config — set projector resolution here
# ---------------------------------------------------------------------------
PROJECTOR_X = 1920    # x-offset of projector in extended desktop
PROJECTOR_Y = 0
PROJECTOR_W = 1920    # projector resolution width  (change if yours is different)
PROJECTOR_H = 1080    # projector resolution height
WINDOW_NAME = "Gus"
SEG_MODEL   = "u2netp"
PAD         = 40
# ---------------------------------------------------------------------------

_lock         = threading.Lock()
_latest_frame = None
_latest_mask  = None
_running      = True
_model_ready  = False
_canvas_size  = [PROJECTOR_W, PROJECTOR_H]   # [w, h], updated when M is pressed


def segmentation_worker():
    global _latest_mask, _model_ready

    print("Loading models...")
    detector    = DogDetector()
    seg_session = new_session(SEG_MODEL)
    _model_ready = True
    print("Models ready.")

    smoothed        = None
    temporal        = 0.6
    morph_k         = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    no_detect_count = 0
    HOLD_FRAMES     = 8
    FADE_RATE       = 0.05

    while _running:
        with _lock:
            frame = _latest_frame.copy() if _latest_frame is not None else None
        if frame is None:
            continue

        h, w = frame.shape[:2]

        boxes = detector.detect(frame)
        if boxes:
            no_detect_count = 0
            raw = np.zeros((h, w), dtype=np.float32)
            boxes.sort(key=lambda b: (b[2]-b[0]) * (b[3]-b[1]), reverse=True)
            x1, y1, x2, y2 = boxes[0]
            x1c = max(0, x1 - PAD);  y1c = max(0, y1 - PAD)
            x2c = min(w, x2 + PAD);  y2c = min(h, y2 + PAD)
            crop = frame[y1c:y2c, x1c:x2c]
            rgba = rembg_remove(crop, session=seg_session)
            raw[y1c:y2c, x1c:x2c] = rgba[:, :, 3].astype(np.float32) / 255.0

            raw_u8 = (raw * 255).astype(np.uint8)
            raw_u8 = cv2.morphologyEx(raw_u8, cv2.MORPH_CLOSE, morph_k)
            raw_u8 = cv2.morphologyEx(raw_u8, cv2.MORPH_OPEN,  morph_k)
            raw    = raw_u8.astype(np.float32) / 255.0
            raw    = cv2.GaussianBlur(raw, (21, 21), 0)

            smoothed = raw.copy() if smoothed is None or smoothed.shape != raw.shape \
                       else temporal * smoothed + (1.0 - temporal) * raw
        else:
            no_detect_count += 1
            if smoothed is not None and no_detect_count > HOLD_FRAMES:
                smoothed = np.clip(smoothed - FADE_RATE, 0, 1)

        with _lock:
            _latest_mask = smoothed.copy() if smoothed is not None else None


def _make_canvas(frame, mask, cw, ch):
    h, w  = frame.shape[:2]
    scale = min(cw / w, ch / h)
    nw, nh = int(w * scale), int(h * scale)
    ox, oy = (cw - nw) // 2, (ch - nh) // 2
    canvas = np.zeros((ch, cw, 3), dtype=np.uint8)

    if mask is not None:
        alpha  = cv2.resize(mask, (w, h))[:, :, np.newaxis]
        gus    = (frame.astype(np.float32) * alpha).astype(np.uint8)
        gus_s  = cv2.resize(gus, (nw, nh))
        mask_s = cv2.resize(mask, (nw, nh))[:, :, np.newaxis]
        canvas[oy:oy+nh, ox:ox+nw] = (gus_s.astype(np.float32) * mask_s).astype(np.uint8)
    else:
        plain = cv2.resize(frame, (nw, nh))
        canvas[oy:oy+nh, ox:ox+nw] = plain
        label = "Loading model..." if not _model_ready else "Waiting for Gus..."
        cv2.putText(canvas, label, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return canvas


async def main():
    global _latest_frame, _running

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, PROJECTOR_W, PROJECTOR_H)
    threading.Thread(target=segmentation_worker, daemon=True).start()

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
    print("Camera ready. Q=quit  M=move to projector")

    try:
        while True:
            # Reconnect loop — keeps retrying on connection loss
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

            with _lock:
                _latest_frame = frame.copy()
                mask = _latest_mask.copy() if _latest_mask is not None else None

            cw, ch = _canvas_size
            canvas = _make_canvas(frame, mask, cw, ch)
            cv2.imshow(WINDOW_NAME, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("m"):
                cv2.moveWindow(WINDOW_NAME, PROJECTOR_X, PROJECTOR_Y)
                cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                _canvas_size[0] = PROJECTOR_W
                _canvas_size[1] = PROJECTOR_H
                print(f"Moved to projector ({PROJECTOR_W}x{PROJECTOR_H})")

            await asyncio.sleep(0.05)
    finally:
        _running = False
        cv2.destroyAllWindows()
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
