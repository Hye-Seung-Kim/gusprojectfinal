# Gus in the Room

A live installation that brings Gus — a dog who lives outside — into the SmartObject classroom through real-time projection. Gus is detected by a camera mounted on a mobile robot, his background is stripped away by a computer vision pipeline, and his silhouette is projected onto the studio wall at full scale. Students in the class can also remotely navigate the robot from a web app, steering where Gus goes and capturing photos of him.

The piece asks what it means to *import* a living thing into a designed system — not as data or metaphor, but as a presence.

---

## System Architecture

```
[Gus, outside]
      │
      │  (VIAM robot + camera)
      ▼
┌─────────────────────────────┐        ┌──────────────────────────┐
│     studio_projection        │        │   viam_remote_control     │
│                             │        │                          │
│  VIAM camera stream         │        │  FastAPI backend         │
│  → YOLOv8 dog detector      │        │  → robot movement API    │
│  → MediaPipe segmentation   │        │  → camera MJPEG stream   │
│  → guided-filter edge       │        │                          │
│  → projector display        │        │  React frontend          │
│                             │        │  → D-pad controls        │
│  [black background,         │        │  → live camera feed      │
│   Gus silhouette only]      │        │  → photo capture         │
└─────────────────────────────┘        └──────────────────────────┘
```

---

## Components

### `studio_projection/` — Projection Pipeline

Runs on a Mac in the studio, connected to an external projector.

| File | Purpose |
|---|---|
| `gus_mediapipe_projection.py` | Main loop: VIAM → detect → segment → project |
| `gus_mediapipe_test.py` | Webcam test version (no VIAM required) |
| `viam_client.py` | VIAM robot connection helper |
| `config.py` | VIAM credentials and camera name |
| `gus.onnx` | Custom YOLOv8 model trained to detect Gus specifically |
| `test_viam.py` | Connection sanity check |

**Pipeline per frame:**
1. Fetch frame from VIAM camera over the network
2. Run `DogDetector` (custom ONNX model) to locate Gus's bounding box
3. Crop the box + padding, run MediaPipe `SelfieSegmenter` inside the crop
4. Expand mask back to full frame, apply guided filter + Gaussian blur for soft edges
5. Gamma-lift the frame (to bring up dark fur), composite against black
6. Display on projector via OpenCV fullscreen window

If Gus walks out of frame, the mask fades out gradually over 15 frames rather than cutting instantly.

**Keyboard controls (projection window):**
| Key | Action |
|---|---|
| `Q` | Quit |
| `M` | Move window to projector (fullscreen) |
| `[` / `]` | Decrease / increase edge softness |

---

### `viam_remote_control/` — Web Remote Control

A full-stack app that lets anyone with the passcode steer Gus's robot and watch the camera from anywhere.

**Backend** (`backend/`, FastAPI + uvicorn):
- `POST /move/{direction}` — forward / backward / left / right / stop
- `GET /camera` — MJPEG stream
- `GET /camera.jpg` — single JPEG snapshot (polled by frontend)
- `GET /capture` — save + download a timestamped photo
- `GET /diagnostics` — connection status and resource list

All endpoints require an `X-Control-Token` header or `?token=` query param.

**Frontend** (`frontend/`, React + Vite):
- Passcode gate — camera and controls stay hidden until the token is entered
- Live camera feed (polls `/camera.jpg` every 750 ms)
- D-pad UI for robot movement
- Capture button to download a photo

---

## Running Locally

### Studio Projection

```bash
cd studio_projection

# Python 3.11 recommended (MediaPipe compatibility)
python -m venv .venv && source .venv/bin/activate
pip install viam-sdk mediapipe opencv-python opencv-contrib-python numpy

python gus_mediapipe_projection.py
```

Press `M` once the window opens to move it to the projector.

To test with a webcam instead of the VIAM camera:

```bash
python gus_mediapipe_test.py
```

### Remote Control Backend

```bash
cd viam_remote_control/backend

cp .env.example .env
# Fill in VIAM_ADDRESS, VIAM_API_KEY, VIAM_API_KEY_ID, CONTROL_TOKEN

pip install -r ../requirements.txt
uvicorn app:app --reload --port 8000
```

### Remote Control Frontend

```bash
cd viam_remote_control/frontend

npm install

# Point at local backend
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

npm run dev
```

---

## Deployment

The backend deploys to **Render**, the frontend to **Vercel**. See [`viam_remote_control/DEPLOY.md`](viam_remote_control/DEPLOY.md) for step-by-step instructions including credential rotation and environment variable setup.

Deployment config is in `render.yaml` at the repo root.

---

## Technical Notes

- **Why a custom ONNX model?** The MediaPipe `SelfieSegmenter` is trained on people. Running it across the full frame on a dog produced noisy, unstable masks. The custom YOLOv8 model (`gus.onnx`) first locates Gus's bounding box; MediaPipe then only processes that crop. This dramatically reduces false positives and keeps segmentation stable.
- **Why guided filter?** Standard Gaussian blur on the mask alone produces soft but inaccurate edges. `cv2.ximgproc.guidedFilter` uses the grayscale image as a guide, preserving fur texture at edges.
- **Why gamma lift?** Gus has dark fur. Compositing the raw frame against black makes him disappear. A gamma of 0.8 lifts midtones before compositing so he reads on the projection surface.
- **Fade on miss:** When Gus leaves frame, the mask decays at `FADE_RATE = 0.08` per frame rather than vanishing instantly, giving a ghosting effect.

---

## Dependencies

| Package | Use |
|---|---|
| `viam-sdk` | Robot and camera connection |
| `mediapipe` | Background segmentation |
| `opencv-contrib-python` | Guided filter (`ximgproc`) |
| `ultralytics` / ONNX | Dog detection |
| `fastapi` + `uvicorn` | Backend API server |
| `Pillow` | Image encoding |
| React + Vite | Frontend UI |
