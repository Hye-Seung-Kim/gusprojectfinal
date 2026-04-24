from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

from robot_control import move, stop
from camera_stream import get_frame
from viam_client import close_robot

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoveCommand(BaseModel):
    linear_x: float = 0.0
    linear_y: float = 0.0
    angular: float = 0.0


@app.post("/move")
async def move_robot(cmd: MoveCommand):
    try:
        await move(cmd.linear_x, cmd.linear_y, cmd.angular)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop")
async def stop_robot():
    try:
        await stop()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/camera")
async def camera_feed():
    async def frame_generator():
        while True:
            frame = await get_frame()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            await asyncio.sleep(0.05)  # ~20 fps

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.on_event("shutdown")
async def shutdown():
    await close_robot()
