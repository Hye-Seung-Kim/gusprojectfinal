"""
export_coreml.py

Converts yolov8n-seg.pt to CoreML format for fast inference on Apple Silicon.
Run once. Takes a few minutes. Output: yolov8n-seg.mlpackage

Usage:
    python export_coreml.py
"""

from ultralytics import YOLO

print("Loading PyTorch model...")
model = YOLO("yolov8n-seg.pt")

print("Exporting to CoreML (this takes a few minutes, once only)...")
model.export(format="coreml", nms=True)

print("\nDone. File saved as: yolov8n-seg.mlpackage")
print("Update YOLO_MODEL in gus_webcam_test.py to: 'yolov8n-seg.mlpackage'")
