import { useState } from "react";
import "./index.css";
import Dashboard from "./pages/Dashboard";
import Datasets from "./pages/Datasets";
import Providers from "./pages/Providers";
import Knowledge from "./pages/Knowledge";
import Predictions from "./pages/Predictions";
import Pattern from "./pages/Pattern";
import Scenario from "./pages/Scenario";
import Risk from "./pages/Risk";
import Health from "./pages/Health";

const TABS = ["dashboard", "datasets", "providers", "knowledge", "predictions", "pattern", "scenario", "risk", "health"] as const;
type Tab = (typeof TABS)[number];

const LABELS: Record<Tab, string> = {
  dashboard: "Início", datasets: "Dados", providers: "Provedores de IA", knowledge: "Aprendizado",
  predictions: "Previsões", pattern: "Padrões", scenario: "Cenários", risk: "Riscos", health: "Saúde do sistema",
};

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>LOKI</h1>
          <span className="sub">Sistema de inteligência preditiva — observe, entenda e preveja seus dados</span>
        </div>
        <nav role="tablist" aria-label="Seções" onKeyDown={(e) => {
          const i = TABS.indexOf(tab);
          if (e.key === "ArrowRight") setTab(TABS[(i + 1) % TABS.length]);
          if (e.key === "ArrowLeft") setTab(TABS[(i + TABS.length - 1) % TABS.length]);
        }}>
          {TABS.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} tabIndex={tab === t ? 0 : -1}
              className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{LABELS[t]}</button>
          ))}
        </nav>
      </header>
      <main className="tab-panel">
        {tab === "dashboard" && <Dashboard />}
        {tab === "datasets" && <Datasets />}
        {tab === "providers" && <Providers />}
        {tab === "knowledge" && <Knowledge />}
        {tab === "predictions" && <Predictions />}
        {tab === "pattern" && <Pattern />}
        {tab === "scenario" && <Scenario />}
        {tab === "risk" && <Risk />}
        {tab === "health" && <Health />}
      </main>
    </div>
  );
}