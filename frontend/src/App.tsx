import { Link, Route, Routes } from "react-router-dom";
import Assistant from "./pages/Assistant";
import Topics from "./pages/Topics";
import AdminOverview from "./pages/AdminOverview";
import "./App.css";

export default function App() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-brand">ShifaHealth AI</span>
        <Link to="/">Assistant</Link>
        <Link to="/topics">Topics</Link>
        <Link to="/admin">Admin Console</Link>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Assistant />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/admin" element={<AdminOverview />} />
        </Routes>
      </main>
    </div>
  );
}
