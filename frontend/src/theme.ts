function hasAnkiThemeClass(): boolean {
  return (
    document.documentElement.classList.contains("night-mode") ||
    document.documentElement.dataset.bsTheme !== undefined ||
    document.body.classList.contains("night_mode") ||
    document.body.classList.contains("nightMode") ||
    document.body.dataset.ankiAiTheme !== undefined
  );
}

function setFallbackTheme(isDark: boolean): void {
  document.documentElement.dataset.ankiAiTheme = isDark ? "dark" : "light";
  document.body.dataset.ankiAiTheme = isDark ? "dark" : "light";
}

export function installThemeSync(): void {
  if (hasAnkiThemeClass()) {
    return;
  }

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  setFallbackTheme(mediaQuery.matches);

  const handleChange = (event: MediaQueryListEvent) => {
    setFallbackTheme(event.matches);
  };

  mediaQuery.addEventListener("change", handleChange);
}
