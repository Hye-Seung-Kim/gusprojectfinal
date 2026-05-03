import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from viam.components.base import Base
from viam.components.camera import Camera
import cv2
import io
import numpy as np
from PIL import Image

from viam_client import connect_robot
from config import BASE_NAME, CAMERA_NAME, CONTROL_TOKEN

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

robot = None
base = None
camera = None
connect_lock = asyncio.Lock()
CAPTURE_DIR = Path(__file__).resolve().parent / "captures"
STEP_DISTANCE_MM = 8
STEP_VELOCITY_MM_S = 35
TURN_ANGLE_DEG = 3
TURN_VELOCITY_DEG_S = 25
OFFLINE_RETRY_SECONDS = 2.0


def token_from_request(request: Request):
    return request.headers.get("x-control-token") or request.query_params.get("token", "")


def require_control_token(request: Request):
    if CONTROL_TOKEN and token_from_request(request) != CONTROL_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    return None


def viam_image_to_cv2(viam_image):
    pil_img = Image.open(io.BytesIO(viam_image.data))
    rgb = np.array(pil_img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


async def get_camera_jpeg():
    await ensure_robot_connected()
    images, _ = await camera.get_images()
    if not images:
        return None

    frame = viam_image_to_cv2(images[0])
    ok, jpeg = cv2.imencode(".jpg", frame)
    if not ok:
        return None

    return jpeg.tobytes()


@app.on_event("startup")
async def startup():
    print("Backend ready. Viam robot will connect when it is online.")


@app.on_event("shutdown")
async def shutdown():
    global robot
    if robot:
        await robot.close()


@app.get("/")
async def root():
    return {
        "status": "backend running",
        "robot": "connected" if robot else "not connected",
    }


async def ensure_robot_connected():
    global robot, base, camera
    if robot and base and camera:
        return

    async with connect_lock:
        if robot and base and camera:
            return

        try:
            robot = await connect_robot()
            base = Base.from_robot(robot=robot, name=BASE_NAME)
            camera = Camera.from_robot(robot=robot, name=CAMERA_NAME)
            print("Connected to Viam robot")
        except Exception:
            robot = None
            base = None
            camera = None
            raise


async def safe_stop():
    try:
        if base:
            await base.stop()
    except Exception as e:
        print("stop error:", e)


async def tiny_move_straight(distance):
    try:
        velocity = STEP_VELOCITY_MM_S if distance > 0 else -STEP_VELOCITY_MM_S
        await base.move_straight(
            distance=distance,
            velocity=velocity,
            timeout=1,
        )
    finally:
        await safe_stop()


async def tiny_spin(angle):
    try:
        velocity = TURN_VELOCITY_DEG_S if angle > 0 else -TURN_VELOCITY_DEG_S
        await base.spin(
            angle=angle,
            velocity=velocity,
            timeout=1,
        )
    finally:
        await safe_stop()


@app.post("/move/{direction}")
async def move(direction: str, request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    try:
        await ensure_robot_connected()

        if direction == "forward":
            await tiny_move_straight(STEP_DISTANCE_MM)
        elif direction == "backward":
            await tiny_move_straight(-STEP_DISTANCE_MM)
        elif direction == "left":
            await tiny_spin(TURN_ANGLE_DEG)
        elif direction == "right":
            await tiny_spin(-TURN_ANGLE_DEG)
        elif direction == "stop":
            await safe_stop()
        else:
            return JSONResponse({"error": "unknown direction"}, status_code=400)

        return {"ok": True, "direction": direction}
    except Exception as e:
        print("move error:", e)
        return JSONResponse({"error": "robot unavailable"}, status_code=503)


@app.get("/diagnostics")
async def diagnostics(request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    try:
        await ensure_robot_connected()
        resources = [
            {
                "namespace": resource.namespace,
                "type": resource.type,
                "subtype": resource.subtype,
                "name": resource.name,
            }
            for resource in robot.resource_names
        ]

        return {
            "ok": True,
            "robot": "connected",
            "base_configured": BASE_NAME,
            "camera_configured": CAMERA_NAME,
            "resources": resources,
        }
    except Exception as e:
        print("diagnostics error:", e)
        return JSONResponse(
            {
                "ok": False,
                "robot": "unavailable",
                "error": str(e),
                "base_configured": BASE_NAME,
                "camera_configured": CAMERA_NAME,
            },
            status_code=503,
        )


async def frame_generator():
    while True:
        try:
            jpeg = await get_camera_jpeg()
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpeg +
                    b"\r\n"
                )
        except Exception as e:
            print("camera error:", e)
            await asyncio.sleep(OFFLINE_RETRY_SECONDS)
            continue

        await asyncio.sleep(0.08)


@app.get("/camera")
async def camera_feed(request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/capture")
async def capture(request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    try:
        jpeg = await get_camera_jpeg()
        if not jpeg:
            return JSONResponse({"error": "no camera image available"}, status_code=503)

        CAPTURE_DIR.mkdir(exist_ok=True)
        filename = f"gus-capture-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
        path = CAPTURE_DIR / filename
        path.write_bytes(jpeg)

        return FileResponse(
            path,
            media_type="image/jpeg",
            filename=filename,
        )
    except Exception as e:
        print("capture error:", e)
        return JSONResponse({"error": "capture failed"}, status_code=500)
