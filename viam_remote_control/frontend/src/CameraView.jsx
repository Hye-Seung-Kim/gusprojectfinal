import { BACKEND_URL, withToken } from "./api";

export default function CameraView({ token }) {
  return (
    <section className="camera-section">
      <img
        className="camera-feed"
        src={withToken(`${BACKEND_URL}/camera`, token)}
        alt="Viam live camera feed"
      />
    </section>
  );
}
