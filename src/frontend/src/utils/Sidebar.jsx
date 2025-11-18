import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import "../css/utils/Sidebar.css";

function Sidebar() {
  const navigate = useNavigate();
  const [, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar_collapsed");
    const isCollapsed = saved === "true";
    setCollapsed(isCollapsed);
    const root = document.documentElement;
    if (isCollapsed) root.classList.add("sidebar-collapsed");
    else root.classList.remove("sidebar-collapsed");
  }, []);

  const handleToggle = useCallback(() => {
    const root = document.documentElement;
    const isCollapsed = root.classList.contains("sidebar-collapsed");
    const next = !isCollapsed;
    if (next) root.classList.add("sidebar-collapsed");
    else root.classList.remove("sidebar-collapsed");
    localStorage.setItem("sidebar_collapsed", String(next));
  }, []);

  const Item = ({ to, icon, label, onClick }) => (
    <li className="sidebar-item">
      <button
        type="button"
        className="sidebar-link"
        onClick={onClick ?? (() => navigate(to))}
      >
        <img className="sidebar-icon" src={icon}/>
        <span className="sidebar-text">{label}</span>
      </button>
    </li>
  );

  return (
    <div className="sidebar" id="sidebar">
      <div className="sidebar-header">
        <button className="sidebar-logo-btn" onClick={() => navigate("/")}>
          <span className="sidebar-logo-text">Doug</span>
        </button>
        <button
          className="sidebar-toggle-btn"
          onClick={handleToggle}
          aria-label="Toggle sidebar"
        >
          <span className="toggle-icon open-icon">☰</span>
          <span className="toggle-icon closed-icon">→</span>
        </button>
      </div>

      <ul className="sidebar-menu">
        <Item to="/" icon="/icons/home.svg" label="Home" />
        <Item to="/tasks" icon="/icons/tasks.svg" label="Tasks" />
      </ul>

      <div className="sidebar-footer">
        <div className="sidebar-footer-content">
          <span className="sidebar-text">Version 1.0.0</span>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;