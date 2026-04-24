import asyncio
import io
import cv2
import numpy as np
from PIL import Image
from viam.components.camera import Camera

from config import CAMERA_NAME
from viam_client import connect_robot


def viam_image_to_cv2(viam_image):
    pil_img = Image.open(io.BytesIO(viam_image.data))
    rgb = np.array(pil_img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


async def main():
    robot = await connect_robot()
    camera = Camera.from_robot(robot=robot, name=CAMERA_NAME)

    print("Connected to camera. Press q to quit.")

    try:
        while True:
            images, _ = await camera.get_images()

            if images:
                frame = viam_image_to_cv2(images[0])
                cv2.imshow("Remote Viam Camera", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            await asyncio.sleep(0.05)

    finally:
        cv2.destroyAllWindows()
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())