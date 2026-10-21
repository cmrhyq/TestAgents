import { Link, useNavigate, useRouteError, isRouteErrorResponse } from "react-router-dom";
import { RefreshCw, LayoutDashboard } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import NotFoundPage from "./not-found.tsx";

function resolveError(error: unknown): { status?: number; title: string; message: string } {
  if (isRouteErrorResponse(error)) {
    return {
      status: error.status,
      title: error.statusText || "请求失败",
      message:
        typeof error.data === "string" && error.data.length > 0
          ? error.data
          : "页面加载失败，请重试。",
    };
  }

  if (error instanceof Error) {
    return {
      title: "出错了",
      message: error.message || "发生了未知错误。",
    };
  }

  return {
    title: "出错了",
    message: "发生了未知错误。",
  };
}

export default function ErrorPage() {
  const error = useRouteError();
  const navigate = useNavigate();

  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundPage />;
  }

  const { status, title, message } = resolveError(error);

  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="space-y-3">
        {status !== undefined && (
          <p className="font-display text-7xl font-semibold tracking-tight text-foreground">
            {status}
          </p>
        )}
        <div className="font-mono text-sm text-destructive">&gt; error: {title.toLowerCase()}</div>
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">{message}</p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button variant="outline" onClick={() => navigate(0)}>
          <RefreshCw className="h-4 w-4" />
          重新加载
        </Button>
        <Button asChild>
          <Link to="/dashboard">
            <LayoutDashboard className="h-4 w-4" />
            前往仪表盘
          </Link>
        </Button>
      </div>
    </div>
  );
}
