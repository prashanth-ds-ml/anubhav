import { createRoot } from "react-dom/client";
import "./tokens.css";
import "./app.css";
import App from "./App";
import { SettingsProvider } from "./lib/ctx";

createRoot(document.getElementById("root")!).render(
  <SettingsProvider>
    <App />
  </SettingsProvider>,
);
