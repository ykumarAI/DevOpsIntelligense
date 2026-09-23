import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import DashboardPage from "./pages/DashboardPage.jsx";
import AccountsPage from "./pages/AccountsPage.jsx";
import ResourcesPage from "./pages/ResourcesPage.jsx";
import GitLabSourcesPage from "./pages/GitLabSourcesPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

const NAV = [
  { section: "Operations" },
  { key: "dashboard", label: "Dashboard" },
  { key: "resources", label: "Monitored Resources" },
  { section: "Sources" },
  { key: "accounts", label: "AWS Accounts" },
  { key: "gitlab", label: "GitLab Sources" },
  { section: "Preferences" },
  { key: "settings", label: "Settings" },
];

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [accounts, setAccounts] = useState([]);
  const [settings, setSettings] = useState(null);

  const loadAccounts = async () => {
    try {
      setAccounts(await api.listAccounts());
    } catch (e) {
      console.error(e);
    }
  };

  const loadSettings = async () => {
    try {
      setSettings(await api.getSettings());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadAccounts();
    loadSettings();
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          Dev<span>Ops</span> Intelligence
          <div className="subtitle">Operational visibility</div>
        </div>
        {NAV.map((item, i) =>
          item.section ? (
            <div className="nav-section" key={`s${i}`}>
              {item.section}
            </div>
          ) : (
            <button
              key={item.key}
              className={`nav-item ${page === item.key ? "active" : ""}`}
              onClick={() => setPage(item.key)}
            >
              {item.label}
            </button>
          )
        )}
      </aside>

      <main className="main">
        {page === "dashboard" && (
          <DashboardPage accounts={accounts} settings={settings} />
        )}
        {page === "resources" && <ResourcesPage accounts={accounts} />}
        {page === "accounts" && (
          <AccountsPage accounts={accounts} onChange={loadAccounts} />
        )}
        {page === "gitlab" && <GitLabSourcesPage />}
        {page === "settings" && (
          <SettingsPage accounts={accounts} onSaved={setSettings} />
        )}
      </main>
    </div>
  );
}
