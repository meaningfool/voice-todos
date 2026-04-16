import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { BenchmarkReportApp } from "./App";
import "./index.css";

function readBootstrapPayload() {
  const element = document.getElementById("benchmark-report-bootstrap");
  const text = element?.textContent ?? "";
  try {
    return JSON.parse(text);
  } catch {
    return {
      reportPath: "(unavailable report path)",
      report: null,
    };
  }
}

const rootElement = document.getElementById("root");

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <BenchmarkReportApp bootstrap={readBootstrapPayload()} />
    </StrictMode>,
  );
}
