import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter/index.css";
import App from "./App";
import "./i18n";
import { initTheme } from "./theme";
import "./styles.css";

initTheme();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
