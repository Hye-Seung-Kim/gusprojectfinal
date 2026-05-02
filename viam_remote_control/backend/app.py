import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from viam.components.base import Base
from viam.components.camera import Camera
import cv2
import io
import numpy as np
from PIL import Image

from viam_client import connect_robot
from config import BASE_NAME, CAMERA_NAME

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

        robot = await connect_robot()
        base = Base.from_robot(robot=robot, name=BASE_NAME)
        camera = Camera.from_robot(robot=robot, name=CAMERA_NAME)
        print("Connected to Viam robot")


@app.post("/move/{direction}")
async def move(direction: str):
    try:
        await ensure_robot_connected()

        if direction == "forward":
            await base.move_straight(distance=30, velocity=25)
        elif direction == "backward":
            await base.move_straight(distance=-30, velocity=25)
        elif direction == "left":
            await base.spin(angle=5, velocity=15)
        elif direction == "right":
            await base.spin(angle=-5, velocity=15)
        elif direction == "stop":
            await base.stop()
        else:
            return JSONResponse({"error": "unknown direction"}, status_code=400)

        await base.stop()
        return {"ok": True, "direction": direction}
    except Exception as e:
        print("move error:", e)
        return JSONResponse({"error": "robot unavailable"}, status_code=503)


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

        await asyncio.sleep(0.08)


@app.get("/camera")
async def camera_feed():
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/capture")
async def capture():
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
