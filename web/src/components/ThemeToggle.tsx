import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";
const KEY = "anubhav-theme";

const system = (): Theme => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const stored = (): Theme | null => {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null; // storage can be blocked (private windows); the toggle still works for this visit
  }
};

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? system());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="theme"
      aria-label={`Switch to ${next} theme`}
      onClick={() => {
        setTheme(next);
        try { localStorage.setItem(KEY, next); } catch { /* ignore */ }
      }}
    >
      {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </button>
  );
}
