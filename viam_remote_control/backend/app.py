import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from viam.components.base import Base
from viam.components.base.base import Vector3
from viam.components.camera import Camera
import io
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
robot_io_lock = asyncio.Lock()
CAPTURE_DIR = Path(__file__).resolve().parent / "captures"
LINEAR_VELOCITY_MM_S = 90
ANGULAR_VELOCITY_DEG_S = 45
MOVE_PULSE_SECONDS = 0.14
MOVE_TIMEOUT_SECONDS = 3
OFFLINE_RETRY_SECONDS = 2.0


def token_from_request(request: Request):
    return request.headers.get("x-control-token") or request.query_params.get("token", "")


def require_control_token(request: Request):
    if CONTROL_TOKEN and token_from_request(request) != CONTROL_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    return None


def viam_image_to_cv2(viam_image):
    pil_img = Image.open(io.BytesIO(viam_image.data))
    return pil_img.convert("RGB")


def encode_jpeg(viam_image):
    if str(viam_image.mime_type) == "image/jpeg":
        return viam_image.data

    img = viam_image_to_cv2(viam_image)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


async def get_camera_jpeg():
    await ensure_robot_connected()

    try:
        async with robot_io_lock:
            images, _ = await camera.get_images(timeout=5)
    except Exception:
        await reset_robot_connection()
        await ensure_robot_connected()
        async with robot_io_lock:
            images, _ = await camera.get_images(timeout=5)

    if not images:
        return None

    return encode_jpeg(images[0])


@app.on_event("startup")
async def startup():
    print("Backend ready. Viam robot will connect when it is online.")


@app.on_event("shutdown")
async def shutdown():
    await reset_robot_connection()


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


async def reset_robot_connection():
    global robot, base, camera
    old_robot = robot

    robot = None
    base = None
    camera = None

    if old_robot:
        try:
            await old_robot.close()
        except Exception as e:
            print("robot close error:", e)


async def safe_stop():
    try:
        if base:
            await base.stop()
    except Exception as e:
        print("stop error:", e)


async def tiny_move_straight(direction):
    async with robot_io_lock:
        try:
            velocity = LINEAR_VELOCITY_MM_S if direction > 0 else -LINEAR_VELOCITY_MM_S
            await base.set_velocity(
                linear=Vector3(x=0, y=velocity, z=0),
                angular=Vector3(x=0, y=0, z=0),
                timeout=MOVE_TIMEOUT_SECONDS,
            )
            await asyncio.sleep(MOVE_PULSE_SECONDS)
        finally:
            await safe_stop()


async def tiny_spin(direction):
    async with robot_io_lock:
        try:
            velocity = ANGULAR_VELOCITY_DEG_S if direction > 0 else -ANGULAR_VELOCITY_DEG_S
            await base.set_velocity(
                linear=Vector3(x=0, y=0, z=0),
                angular=Vector3(x=0, y=0, z=velocity),
                timeout=MOVE_TIMEOUT_SECONDS,
            )
            await asyncio.sleep(MOVE_PULSE_SECONDS)
        finally:
            await safe_stop()


@app.post("/move/{direction}")
async def move(direction: str, request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    async def run_move():
        await ensure_robot_connected()

        if direction == "forward":
            await tiny_move_straight(1)
        elif direction == "backward":
            await tiny_move_straight(-1)
        elif direction == "left":
            await tiny_spin(1)
        elif direction == "right":
            await tiny_spin(-1)
        elif direction == "stop":
            async with robot_io_lock:
                await safe_stop()
        else:
            return JSONResponse({"error": "unknown direction"}, status_code=400)

        return {"ok": True, "direction": direction}

    try:
        return await run_move()
    except Exception as e:
        print("move error:", e)
        try:
            await reset_robot_connection()
            return await run_move()
        except Exception as retry_error:
            print("move retry error:", retry_error)
            await reset_robot_connection()
            return JSONResponse({"error": "robot unavailable"}, status_code=503)


@app.get("/diagnostics")
async def diagnostics(request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    try:
        await ensure_robot_connected()
        try:
            await robot.refresh()
        except Exception:
            await reset_robot_connection()
            await ensure_robot_connected()
            await robot.refresh()

        resources = resource_list()

        return {
            "ok": True,
            "robot": "connected",
            "base_configured": BASE_NAME,
            "camera_configured": CAMERA_NAME,
            "resources": resources,
        }
    except Exception as e:
        print("diagnostics error:", e)
        await reset_robot_connection()
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


def resource_list():
    return [
        {
            "namespace": resource.namespace,
            "type": resource.type,
            "subtype": resource.subtype,
            "name": resource.name,
        }
        for resource in robot.resource_names
    ]


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


@app.get("/camera.jpg")
async def camera_snapshot(request: Request):
    unauthorized = require_control_token(request)
    if unauthorized:
        return unauthorized

    try:
        jpeg = await get_camera_jpeg()
        if not jpeg:
            return JSONResponse({"error": "no camera image available"}, status_code=503)

        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, max-age=0",
            },
        )
    except Exception as e:
        print("camera snapshot error:", e)
        return JSONResponse({"error": "camera unavailable"}, status_code=503)


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
