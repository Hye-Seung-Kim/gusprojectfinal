import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()

VIAM_ADDRESS = os.environ["VIAM_ADDRESS"]
VIAM_API_KEY = os.environ["VIAM_API_KEY"]
VIAM_API_KEY_ID = os.environ["VIAM_API_KEY_ID"]
CONTROL_TOKEN = os.getenv("CONTROL_TOKEN", "")

BASE_NAME = "viam_base"
CAMERA_NAME = "cam"
