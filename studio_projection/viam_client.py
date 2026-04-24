from viam.robot.client import RobotClient
from viam.components.camera import Camera

from config import (
    VIAM_ADDRESS,
    VIAM_API_KEY,
    VIAM_API_KEY_ID,
    CAMERA_NAME,
)

async def connect_robot():
    opts = RobotClient.Options.with_api_key(
        api_key=VIAM_API_KEY,
        api_key_id=VIAM_API_KEY_ID,
    )
    robot = await RobotClient.at_address(VIAM_ADDRESS, opts)
    return robot

async def get_camera_handle(robot):
    camera = Camera.from_robot(robot, CAMERA_NAME)
    return camera
