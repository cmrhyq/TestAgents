import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, LayoutDashboard } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="space-y-3">
        <p className="font-display text-7xl font-semibold tracking-tight text-foreground">404</p>
        <div className="font-mono text-sm text-primary">&gt; route not found</div>
        <h1 className="text-lg font-semibold text-foreground">页面未找到</h1>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">
          你访问的页面不存在或可能已被移动。请检查网址，或返回到已知的页面。
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
          返回上一页
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
