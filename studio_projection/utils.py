import cv2
import numpy as np

def viam_image_to_cv2(viam_image):
    """Convert a VIAM image object to a BGR numpy array for OpenCV."""
    arr = np.frombuffer(viam_image.data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame
