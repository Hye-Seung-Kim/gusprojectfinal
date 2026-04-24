const BACKEND_URL = "http://localhost:8000";

export default function CameraView() {
  return (
    <section className="camera-section">
      <h2>Live Camera</h2>
      <img
        className="camera-feed"
        src={`${BACKEND_URL}/camera`}
        alt="Viam live camera feed"
      />
    </section>
  );
}