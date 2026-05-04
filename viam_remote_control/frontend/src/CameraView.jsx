import { useEffect, useMemo, useState } from "react";
import { BACKEND_URL, withToken } from "./api";

export default function CameraView({ token }) {
  const [frameKey, setFrameKey] = useState(0);
  const [cameraState, setCameraState] = useState("loading");
  const cameraUrl = useMemo(
    () => withToken(`${BACKEND_URL}/camera.jpg?t=${frameKey}`, token),
    [frameKey, token],
  );

  useEffect(() => {
    if (cameraState === "offline") {
      return undefined;
    }

    const interval = window.setInterval(() => {
      setFrameKey(Date.now());
    }, 750);

    return () => window.clearInterval(interval);
  }, [cameraState]);

  const retryCamera = () => {
    setCameraState("loading");
    setFrameKey(Date.now());
  };

  return (
    <section className="camera-section">
      <div className="camera-frame">
        <img
          className="camera-feed"
          src={cameraUrl}
          alt="Viam live camera feed"
          onLoad={() => setCameraState("live")}
          onError={() => setCameraState("offline")}
        />
        {cameraState === "offline" && (
          <div className="camera-overlay">
            <p>Camera connection unavailable.</p>
            <button type="button" onClick={retryCamera}>
              Retry camera
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
