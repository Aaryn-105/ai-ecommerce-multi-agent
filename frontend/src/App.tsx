/** App Shell — root layout with Sidebar + Router outlet. */
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatInterface from "./components/ChatInterface";
import Dashboard from "./components/Dashboard";
import ReportList from "./components/ReportList";
import ReportDetail from "./components/ReportDetail";
import ProductBrowser from "./components/ProductBrowser";
import "./components/ChatInterface.css";
import "./App.css";
import "./ReportList.css";
import "./Dashboard.css";
import "./ProductBrowser.css";


function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatInterface />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/reports" element={<ReportList />} />
          <Route path="/report/:id" element={<ReportDetail />} />
          <Route path="/products" element={<ProductBrowser />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}