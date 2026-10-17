import { BrowserRouter, Routes, Route } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import ValidatePage from "./pages/ValidatePage";
import ReportDetail from "./pages/ReportDetail";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <header className="app-header">
          <h1>Prism Lens</h1>
          <p className="subtitle">
            Diagnostic tool for Cursor plugins
          </p>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/validate" element={<ValidatePage />} />
            <Route path="/reports/:reportId" element={<ReportDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;