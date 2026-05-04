import { useEffect, useMemo, useState } from "react";
import { BACKEND_URL, withToken } from "./api";

export default function CameraView({ token }) {
  const [frameKey, setFrameKey] = useState(0);
  const cameraUrl = useMemo(
    () => withToken(`${BACKEND_URL}/camera.jpg?t=${frameKey}`, token),
    [frameKey, token],
  );

  useEffect(() => {
    const interval = window.setInterval(() => {
      setFrameKey(Date.now());
    }, 750);

    return () => window.clearInterval(interval);
  }, []);

  return (
    <section className="camera-section">
      <img
        className="camera-feed"
        src={cameraUrl}
        alt="Viam live camera feed"
      />
    </section>
  );
}
