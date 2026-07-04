import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { Queue } from "./pages/Queue";
import { Review } from "./pages/Review";
import { EvalDashboard } from "./pages/EvalDashboard";
import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <nav className="top-nav">
          <div className="brand">Clinical Intake Agent</div>
          <NavLink to="/" end>
            Queue
          </NavLink>
          <NavLink to="/eval">Eval Dashboard</NavLink>
        </nav>
        <main>
          <Routes>
            <Route path="/" element={<Queue />} />
            <Route path="/review/:id" element={<Review />} />
            <Route path="/eval" element={<EvalDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
