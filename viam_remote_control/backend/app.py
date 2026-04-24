import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
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
)

robot = None
base = None
camera = None


def viam_image_to_cv2(viam_image):
    pil_img = Image.open(io.BytesIO(viam_image.data))
    rgb = np.array(pil_img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


@app.on_event("startup")
async def startup():
    global robot, base, camera
    robot = await connect_robot()
    base = Base.from_robot(robot=robot, name=BASE_NAME)
    camera = Camera.from_robot(robot=robot, name=CAMERA_NAME)
    print("Connected to Viam robot")


@app.on_event("shutdown")
async def shutdown():
    global robot
    if robot:
        await robot.close()


@app.get("/")
async def root():
    return {"status": "backend running"}


@app.post("/move/{direction}")
async def move(direction: str):
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


async def frame_generator():
    while True:
        try:
            images, _ = await camera.get_images()
            if images:
                frame = viam_image_to_cv2(images[0])
                _, jpeg = cv2.imencode(".jpg", frame)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpeg.tobytes() +
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