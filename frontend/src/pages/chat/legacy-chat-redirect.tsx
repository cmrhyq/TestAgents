import { Navigate, useSearchParams } from "react-router-dom";

/**
 * 旧对话入口兼容组件。
 *
 * 把 `/chat?space_id=x&conversation_id=y` 这类历史链接映射到 `/spaces/x/chat?conversation_id=y`；
 * 缺少 `space_id` 时回退到仪表盘。独立成文件以满足 react-refresh 对路由文件的约束。
 */
export function LegacyChatRedirect() {
  const [searchParams] = useSearchParams();
  const spaceId = searchParams.get("space_id");
  if (!spaceId) {
    return <Navigate to="/dashboard" replace />;
  }
  const next = new URLSearchParams(searchParams);
  next.delete("space_id");
  const query = next.toString();
  return <Navigate to={`/spaces/${spaceId}/chat${query ? `?${query}` : ""}`} replace />;
}
