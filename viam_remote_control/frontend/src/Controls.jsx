const API_BASE = "http://localhost:8000";

async function sendMove(linear_x, linear_y, angular) {
  await fetch(`${API_BASE}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ linear_x, linear_y, angular }),
  });
}

async function sendStop() {
  await fetch(`${API_BASE}/stop`, { method: "POST" });
}

const btnStyle = {
  padding: "0.75rem 1.5rem",
  fontSize: "1rem",
  cursor: "pointer",
};

export default function Controls() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 80px)", gap: "0.5rem", textAlign: "center" }}>
      <div />
      <button style={btnStyle} onMouseDown={() => sendMove(0.5, 0, 0)} onMouseUp={sendStop}>
        ▲
      </button>
      <div />

      <button style={btnStyle} onMouseDown={() => sendMove(0, 0, 1)} onMouseUp={sendStop}>
        ◀
      </button>
      <button style={btnStyle} onClick={sendStop}>
        ■
      </button>
      <button style={btnStyle} onMouseDown={() => sendMove(0, 0, -1)} onMouseUp={sendStop}>
        ▶
      </button>

      <div />
      <button style={btnStyle} onMouseDown={() => sendMove(-0.5, 0, 0)} onMouseUp={sendStop}>
        ▼
      </button>
      <div />
    </div>
  );
}
