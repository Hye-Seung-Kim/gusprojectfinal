import { useState } from "react";
import CameraView from "./CameraView";
import Controls from "./Controls";
import { storedToken } from "./api";
import "./App.css";

function App() {
  const [token, setToken] = useState(storedToken);

  const updateToken = (event) => {
    const nextToken = event.target.value.trim();

    setToken(nextToken);
    localStorage.setItem("gus-control-token", nextToken);
  };

  return (
    <div className="app">
      <header>
        <div>
          <h1>Gus Remote Control</h1>
          <p>Kathy’s room → Studio projection system</p>
        </div>

        <label className="token-field">
          <span>Passcode</span>
          <input
            type="password"
            value={token}
            autoComplete="current-password"
            onChange={updateToken}
          />
        </label>
      </header>

      <main>
        <CameraView token={token} />
        <Controls token={token} />
      </main>
    </div>
  );
}

export default App;
