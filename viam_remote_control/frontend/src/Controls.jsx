const BACKEND_URL = "http://localhost:8000";

export default function Controls() {
  const move = async (direction) => {
    await fetch(`${BACKEND_URL}/move/${direction}`, {
      method: "POST",
    });
  };

  return (
    <section className="controls">
      <h2>Robot Control</h2>

      <div className="control-grid">
        <button onClick={() => move("forward")}>↑ Forward</button>
        <button onClick={() => move("left")}>← Left</button>
        <button className="stop" onClick={() => move("stop")}>Stop</button>
        <button onClick={() => move("right")}>Right →</button>
        <button onClick={() => move("backward")}>↓ Backward</button>
      </div>
    </section>
  );
}