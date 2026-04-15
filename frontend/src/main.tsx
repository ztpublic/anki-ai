import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { installBridgeReceiver } from "./bridge";
import "./styles.css";

installBridgeReceiver();

const rootElement = document.getElementById("anki-ai-root");

if (rootElement) {
  createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
