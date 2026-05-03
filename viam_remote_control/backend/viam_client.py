from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions

from config import (
    VIAM_ADDRESS,
    VIAM_API_KEY,
    VIAM_API_KEY_ID,
)

async def connect_robot():
    opts = RobotClient.Options(
        refresh_interval=0,
        check_connection_interval=0,
        attempt_reconnect_interval=0,
        dial_options=DialOptions.with_api_key(
            api_key=VIAM_API_KEY,
            api_key_id=VIAM_API_KEY_ID,
        ),
    )

    robot = await RobotClient.at_address(VIAM_ADDRESS, opts)
    return robot
