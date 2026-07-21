/** Sidebar navigation component. */
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/products", label: "产品目录", icon: "🛍️" },
  { path: "/chat", label: "对话分析", icon: "💬" },
  { path: "/dashboard", label: "数据看板", icon: "📊" },
  { path: "/reports", label: "历史报告", icon: "📄" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>电商智能分析</h2>
        <span className="sidebar-subtitle">Multi-Agent System</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `sidebar-link${isActive ? " active" : ""}`
            }
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span className="sidebar-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="version">v1.0.0</span>
      </div>
    </aside>
  );
}
