import { useState } from "react";
import { BACKEND_URL } from "./api";

const directions = {
  forward: "up",
  right: "right",
  backward: "down",
  left: "left",
};

export default function Controls() {
  const [busyDirection, setBusyDirection] = useState("");
  const [captureState, setCaptureState] = useState("idle");

  const sendCommand = async (direction) => {
    setBusyDirection(direction);
    try {
      const response = await fetch(`${BACKEND_URL}/move/${direction}`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Move failed: ${response.status}`);
      }
    } finally {
      setBusyDirection("");
    }
  };

  const capturePhoto = async () => {
    setCaptureState("saving");

    try {
      const response = await fetch(`${BACKEND_URL}/capture`);

      if (!response.ok) {
        throw new Error(`Capture failed: ${response.status}`);
      }

      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `gus-capture-${Date.now()}.jpg`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setCaptureState("saved");
      window.setTimeout(() => setCaptureState("idle"), 1600);
    } catch (error) {
      console.error(error);
      setCaptureState("error");
    }
  };

  return (
    <section className="controls">
      <div className="dpad" aria-label="Robot direction controls">
        {Object.entries(directions).map(([direction, label]) => (
          <button
            key={direction}
            className={`dpad-button ${direction}`}
            type="button"
            aria-label={direction}
            data-active={busyDirection === direction}
            onClick={() => sendCommand(direction)}
          >
            <span>{label}</span>
          </button>
        ))}
        <div className="dpad-center" aria-hidden="true" />
      </div>

      <div className="action-row">
        <button className="stop-button" type="button" onClick={() => sendCommand("stop")}>
          Stop
        </button>
        <button
          className="capture-button"
          type="button"
          onClick={capturePhoto}
          disabled={captureState === "saving"}
        >
          {captureState === "saving" ? "Saving..." : "Capture"}
        </button>
      </div>

      <p className="status" role="status">
        {captureState === "saved" && "Photo saved"}
        {captureState === "error" && "Capture failed"}
      </p>
    </section>
  );
}
