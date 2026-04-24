const API_BASE = "http://localhost:8000";

export default function CameraView() {
  return (
    <div>
      <img
        src={`${API_BASE}/camera`}
        alt="Robot camera feed"
        style={{ width: "640px", height: "480px", border: "1px solid #ccc" }}
      />
    </div>
  );
}
