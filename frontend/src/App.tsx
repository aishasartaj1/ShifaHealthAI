import { Link, Route, Routes } from "react-router-dom";
import Assistant from "./pages/Assistant";
import Topics from "./pages/Topics";
import AdminOverview from "./pages/AdminOverview";
import AgentObservability from "./pages/AgentObservability";
import Governance from "./pages/Governance";
import "./App.css";

export default function App() {
  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-brand">ShifaHealth AI</span>
        <Link to="/">Assistant</Link>
        <Link to="/topics">Topics</Link>
        <Link to="/admin">Admin</Link>
        <Link to="/admin/agents">Agent Observability</Link>
        <Link to="/admin/governance">Governance</Link>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Assistant />} />
          <Route path="/topics" element={<Topics />} />
          <Route path="/admin" element={<AdminOverview />} />
          <Route path="/admin/agents" element={<AgentObservability />} />
          <Route path="/admin/governance" element={<Governance />} />
        </Routes>
      </main>
    </div>
  );
}
