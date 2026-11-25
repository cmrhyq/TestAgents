import { useEffect } from "react";

const DEFAULT_TITLE = "TestAgents · API 智能测试平台";

/** 设置当前页面的浏览器标题，卸载时恢复站点默认标题。 */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · TestAgents` : DEFAULT_TITLE;
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [title]);
}
