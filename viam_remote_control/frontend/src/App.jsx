import CameraView from "./CameraView";
import Controls from "./Controls";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header>
        <h1>Gus Remote Control</h1>
        <p>Kathy’s room → Studio projection system</p>
      </header>

      <main>
        <CameraView />
        <Controls />
      </main>
    </div>
  );
}

export default App;