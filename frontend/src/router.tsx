import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "./components/layout/app-layout";
import ErrorPage from "./pages/error/error-page.tsx";
import NotFoundPage from "./pages/error/not-found.tsx";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        errorElement: <ErrorPage />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          {
            path: "dashboard",
            lazy: async () => {
              const { default: Component } = await import("./pages/dashboard");
              return { Component };
            },
          },
          {
            path: "spaces",
            lazy: async () => {
              const { default: Component } = await import("./pages/space/spaces.tsx");
              return { Component };
            },
          },
          {
            path: "spaces/:id",
            lazy: async () => {
              const { default: Component } = await import("./pages/space/space-detail.tsx");
              return { Component };
            },
          },
          {
            path: "spaces/:id/endpoints",
            element: <Navigate to=".." replace relative="path" />,
          },
          {
            path: "spaces/:id/environments",
            element: <Navigate to=".." replace relative="path" />,
          },
          {
            path: "spaces/:id/runs",
            element: <Navigate to=".." replace relative="path" />,
          },
          {
            path: "runs/:id",
            lazy: async () => {
              const { default: Component } = await import("./pages/run/run-detail.tsx");
              return { Component };
            },
          },
          {
            path: "chat",
            lazy: async () => {
              const { default: Component } = await import("./pages/chat/chat.tsx");
              return { Component };
            },
          },
          {
            path: "skills",
            lazy: async () => {
              const { default: Component } = await import("./pages/skills/skills.tsx");
              return { Component };
            },
          },
          {
            // 旧路径兜底：/workflows/chat 是历史入口，书签里可能还在，重定向而不是 404
            path: "workflows/chat",
            element: <Navigate to="/chat" replace />,
          },
          {
            path: "workflows/run",
            element: <Navigate to="/chat" replace />,
          },
          {
            path: "reports",
            lazy: async () => {
              const { default: Component } = await import("./pages/report/reports.tsx");
              return { Component };
            },
          },
          {
            // 报告以 run 为单位：路由参数就是 run_id
            path: "reports/:runId",
            lazy: async () => {
              const { default: Component } = await import("./pages/report/report-view.tsx");
              return { Component };
            },
          },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);
