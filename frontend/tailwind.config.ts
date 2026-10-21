import type { Config } from "tailwindcss";

/**
 * 圆角 / 阴影 / 字体 / 颜色令牌已迁移到 src/index.css 的 @theme（Tailwind v4 CSS-first）。
 * 此处仅保留无法用 @theme 表达的历史配置（borderWidth 与动画 keyframes）。
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderWidth: {
        thin: "1px",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "cursor-blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "cursor-blink": "cursor-blink 1s step-end infinite",
      },
    },
  },
} satisfies Config;
