import CameraView from "./CameraView";
import Controls from "./Controls";

export default function App() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem", padding: "1rem" }}>
      <h1>Viam Remote Control</h1>
      <CameraView />
      <Controls />
    </div>
  );
}
