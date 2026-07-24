import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Camera from "./pages/Camera";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"       element={<Dashboard />} />
        <Route path="/camera" element={<Camera />} />
        {/* Additional routes added per feature */}
      </Routes>
    </BrowserRouter>
  );
}
