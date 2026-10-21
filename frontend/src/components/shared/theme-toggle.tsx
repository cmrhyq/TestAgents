import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

/** 顶栏主题切换按钮：亮色图纸 ⇄ 暗色夜图。 */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      aria-label={isDark ? "切换到亮色图纸" : "切换到暗色夜图"}
      title={isDark ? "切换到亮色图纸" : "切换到暗色夜图"}
      className="text-muted-foreground transition-colors hover:text-foreground"
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
