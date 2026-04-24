import asyncio
from viam.components.base import Base
from viam.components.base.base import Vector3

from config import BASE_NAME
from viam_client import connect_robot


LINEAR_POWER = 0.08      # 0.0 ~ 1.0, 아주 약하게
ANGULAR_POWER = 0.08     # 회전도 약하게
PULSE_SECONDS = 0.08     # 움직이는 시간, 더 줄이면 더 조금 움직임


async def safe_stop(base):
    try:
        await base.stop()
    except Exception as e:
        print(f"Stop failed: {e}")


async def pulse_move(base, linear_y=0.0, angular_z=0.0):
    """
    Short pulse movement:
    linear_y: forward/backward
    angular_z: left/right rotation
    """
    try:
        await base.set_power(
            linear=Vector3(x=0, y=linear_y, z=0),
            angular=Vector3(x=0, y=0, z=angular_z),
        )
        await asyncio.sleep(PULSE_SECONDS)
    finally:
        await safe_stop(base)


async def main():
    robot = await connect_robot()
    base = Base.from_robot(robot=robot, name=BASE_NAME)

    print("Connected to Viam robot.")
    print("Controls:")
    print("  w = tiny forward pulse")
    print("  s = tiny backward pulse")
    print("  a = tiny left turn")
    print("  d = tiny right turn")
    print("  x = stop")
    print("  q = stop and quit")

    try:
        while True:
            key = input("Command: ").strip().lower()

            if key == "w":
                print("Tiny forward pulse...")
                await pulse_move(base, linear_y=LINEAR_POWER)

            elif key == "s":
                print("Tiny backward pulse...")
                await pulse_move(base, linear_y=-LINEAR_POWER)

            elif key == "a":
                print("Tiny left turn...")
                await pulse_move(base, angular_z=ANGULAR_POWER)

            elif key == "d":
                print("Tiny right turn...")
                await pulse_move(base, angular_z=-ANGULAR_POWER)

            elif key == "x":
                print("Stopping...")
                await safe_stop(base)

            elif key == "q":
                print("Stopping and quitting...")
                await safe_stop(base)
                break

            else:
                print("Unknown command. Use w/s/a/d/x/q.")

    finally:
        await safe_stop(base)
        await robot.close()
        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())