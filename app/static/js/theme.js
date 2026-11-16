"use strict";

// Loaded synchronously in <head> so the theme is applied before first paint.
(function initTheme() {
  const STORAGE_KEY = "gr-theme";
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const listeners = new Set();

  function readStored() {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch {
      return null;
    }
  }

  function writeStored(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Storage unavailable (private mode, blocked site data): keep in memory.
    }
  }

  function resolve() {
    return readStored() || (media.matches ? "dark" : "light");
  }

  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    listeners.forEach((listener) => listener(theme));
  }

  media.addEventListener("change", () => {
    if (!readStored()) {
      apply(resolve());
    }
  });

  window.GrTheme = {
    get: () => document.documentElement.dataset.theme || "light",
    set(theme) {
      writeStored(theme);
      apply(theme);
    },
    toggle() {
      this.set(this.get() === "dark" ? "light" : "dark");
    },
    onChange(listener) {
      listeners.add(listener);
    },
  };

  apply(resolve());
})();
