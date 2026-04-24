import asyncio
from viam.components.base import Base

from config import BASE_NAME
from viam_client import connect_robot


STEP_DISTANCE = 10      # mm = 3cm
STEP_VELOCITY = 15      # slow speed
TURN_ANGLE = 5          # degrees
TURN_VELOCITY = 15      # slow turn


async def safe_stop(base):
    try:
        await base.stop()
    except Exception as e:
        print(f"Stop failed: {e}")


async def main():
    robot = await connect_robot()
    base = Base.from_robot(robot=robot, name=BASE_NAME)

    print("Connected to Viam robot.")
    print("Controls:")
    print("  w = small step forward")
    print("  s = small step backward")
    print("  a = small turn left")
    print("  d = small turn right")
    print("  x = stop")
    print("  q = stop and quit")

    try:
        while True:
            key = input("Command: ").strip().lower()

            if key == "w":
                print("Small forward step...")
                await base.move_straight(distance=STEP_DISTANCE, velocity=STEP_VELOCITY)
                await safe_stop(base)

            elif key == "s":
                print("Small backward step...")
                await base.move_straight(distance=-STEP_DISTANCE, velocity=STEP_VELOCITY)
                await safe_stop(base)

            elif key == "a":
                print("Small left turn...")
                await base.spin(angle=TURN_ANGLE, velocity=TURN_VELOCITY)
                await safe_stop(base)

            elif key == "d":
                print("Small right turn...")
                await base.spin(angle=-TURN_ANGLE, velocity=TURN_VELOCITY)
                await safe_stop(base)

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