import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type ThemeId = "pink" | "biz";

/** User-facing name of the professional theme. Change here to rename it. */
export const BIZ_THEME_NAME = "Carbon";

const STORAGE_KEY = "maads-theme";

// The business theme is clean & professional, so decorative emoji/pictographs
// are stripped from labels. (Variation selectors, ZWJ and keycaps included.)
const EMOJI_RE = /[\p{Extended_Pictographic}\u{FE0F}\u{200D}\u{20E3}]/gu;

function getInitialTheme(): ThemeId {
  const saved = localStorage.getItem(STORAGE_KEY);
  // Default to the professional Carbon (biz) theme for first-time visitors.
  return saved === "biz" || saved === "pink" ? saved : "biz";
}

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
  /** Text as-is in the pink theme; emoji stripped in the business theme. */
  clean: (text: string) => string;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeId>(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const clean =
    theme === "biz"
      ? (text: string) =>
          text.replace(EMOJI_RE, "").replace(/\s{2,}/g, " ").trim()
      : (text: string) => text;

  return (
    <ThemeContext.Provider value={{ theme, setTheme, clean }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
