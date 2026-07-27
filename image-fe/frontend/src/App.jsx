import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ImagesPage from "./pages/ImagesPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  return (
    <div className="app">
      <h1>AI Image Server</h1>
      <nav className="tabs">
        <NavLink to="/images" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Images
        </NavLink>
        <NavLink to="/chat" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Chat
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/images" replace />} />
        <Route path="/images" element={<ImagesPage />} />
        <Route path="/chat/*" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/images" replace />} />
      </Routes>
    </div>
  );
}
