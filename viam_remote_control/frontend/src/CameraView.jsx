import { BACKEND_URL } from "./api";

export default function CameraView() {
  return (
    <section className="camera-section">
      <img
        className="camera-feed"
        src={`${BACKEND_URL}/camera`}
        alt="Viam live camera feed"
      />
    </section>
  );
}
