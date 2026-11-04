import { useCallback, useEffect, useState } from "react";

/** 主题取值：亮色或暗色。 */
export type Theme = "light" | "dark";

const STORAGE_KEY = "lta-theme";

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage 不可用时回退默认值
  }
  return "light"; // 默认亮色
}

/**
 * 主题状态：默认亮色，暗色通过 `html.dark` 类切换。
 *
 * 仅在用户显式切换时写入 localStorage；未显式选择时跟随系统偏好。
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // 用户未显式选择时，跟随系统亮暗偏好变化
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      try {
        if (!localStorage.getItem(STORAGE_KEY)) {
          setThemeState(e.matches ? "dark" : "light");
        }
      } catch {
        // 忽略存储读取异常
      }
    };
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // 忽略存储写入异常
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // 忽略存储写入异常
      }
      return next;
    });
  }, []);

  return { theme, setTheme, toggleTheme };
}
