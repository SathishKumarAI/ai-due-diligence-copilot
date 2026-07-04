"use client";

import { useEffect, useState } from "react";

// Persists the light/dark choice and applies it before paint via a tiny inline
// script in the layout, so there's no flash of the wrong theme.
export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable — ignore */
    }
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="surface rounded-lg border px-2.5 py-1.5 text-sm transition hover:opacity-80"
      title={dark ? "Switch to light" : "Switch to dark"}
    >
      {dark ? "☀" : "☾"}
    </button>
  );
}
