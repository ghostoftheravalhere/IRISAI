import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Camera from "./pages/Camera";
import Calibration from "./pages/Calibration";
import Voice from "./pages/Voice";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"       element={<Dashboard />} />
        <Route path="/camera" element={<Camera />} />
        <Route path="/calibration" element={<Calibration />} />
        <Route path="/voice" element={<Voice />} />
      </Routes>
    </BrowserRouter>
  );
}
