import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

import { useSpace } from "@/hooks/use-spaces.ts";
import { useDeleteEndpoint } from "@/hooks/use-endpoints.ts";
import { useDeleteEnvironment } from "@/hooks/use-environments.ts";
import { useDocumentTitle } from "@/hooks/use-document-title.ts";
import { Button } from "@/components/ui/button.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { DetailPageSkeleton } from "@/components/shared/detail-page-skeleton.tsx";
import { EndpointFormDialog } from "@/components/endpoint/endpoint-form-dialog.tsx";
import { EnvironmentFormDialog } from "@/components/environment/environment-form-dialog.tsx";
import type { Endpoint, Environment } from "@/lib/types.ts";
import { EndpointsTab } from "./tabs/endpoints-tab";
import { EnvironmentsTab } from "./tabs/environments-tab";
import { AgentRunsTab } from "./tabs/agent-runs-tab";
import { OverviewTab } from "./tabs/overview-tab";
import { ConversationsTab } from "./tabs/conversations-tab";
import { MemoriesTab } from "./tabs/memories-tab";
import { KnowledgeTab } from "./tabs/knowledge-tab";

const SPACE_STATUS_MAP: Record<number, string> = {
  0: "未启用",
  1: "已启用",
};

/**
 * 空间详情页：概览、会话、接口、环境、记忆、知识库与执行记录。
 *
 * 各 tab 的数据查询下沉在 tab 组件内部，只有切到对应 tab（组件挂载）时才发起请求；
 * 筛选与分页状态留在本组件，切换 tab 不会丢失。
 */
export default function SpaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const spaceId = id || "";

  const { data: space, isLoading: spaceLoading } = useSpace(spaceId);

  useDocumentTitle(spaceLoading ? "空间详情" : (space?.name ?? "空间详情"));

  const [endpointPage, setEndpointPage] = useState(1);
  const [agentRunPage, setAgentRunPage] = useState(1);
  const [endpointKeyword, setEndpointKeyword] = useState("");
  const [endpointTags, setEndpointTags] = useState<string[]>([]);
  const [endpointTagsMode, setEndpointTagsMode] = useState<"any" | "all">("any");

  // 筛选条件变化时回到第 1 页。放在事件回调里而不是 effect 中，避免级联渲染
  const handleKeywordChange = (value: string) => {
    setEndpointKeyword(value);
    setEndpointPage(1);
  };
  const handleTagsChange = (tags: string[]) => {
    setEndpointTags(tags);
    setEndpointPage(1);
  };
  const handleTagsModeChange = (mode: "any" | "all") => {
    setEndpointTagsMode(mode);
    setEndpointPage(1);
  };

  const deleteEndpoint = useDeleteEndpoint();
  const deleteEnvironment = useDeleteEnvironment();

  const [endpointDialogOpen, setEndpointDialogOpen] = useState(false);
  const [editingEndpoint, setEditingEndpoint] = useState<Endpoint | null>(null);
  const [envDialogOpen, setEnvDialogOpen] = useState(false);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);

  if (spaceLoading) {
    return <DetailPageSkeleton />;
  }

  if (!space) {
    return (
      <EmptyState
        title="未找到空间"
        description="你查找的空间不存在或已被删除。"
        action={
          <Button variant="outline" onClick={() => navigate("/")}>
            返回仪表盘
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={space.name}
        annotation={`空间 ${String(space.id)}`}
        meta={
          <Badge variant={space.status === 1 ? "success" : "secondary"}>
            {SPACE_STATUS_MAP[space.status] ?? "未知"}
          </Badge>
        }
        description={space.description || undefined}
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={`/spaces/${spaceId}/chat`}>
              <Sparkles className="h-3.5 w-3.5" />
              开始对话
            </Link>
          </Button>
        }
      />

      <Tabs defaultValue="overview" className="w-full">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="conversations">会话</TabsTrigger>
          <TabsTrigger value="endpoints">接口</TabsTrigger>
          <TabsTrigger value="environments">环境</TabsTrigger>
          <TabsTrigger value="memories">记忆</TabsTrigger>
          <TabsTrigger value="knowledge">知识库</TabsTrigger>
          <TabsTrigger value="agent-runs">执行记录</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <OverviewTab spaceId={spaceId} />
        </TabsContent>

        <TabsContent value="conversations" className="space-y-4">
          <ConversationsTab spaceId={spaceId} />
        </TabsContent>

        <TabsContent value="endpoints" className="space-y-4">
          <EndpointsTab
            spaceId={spaceId}
            keyword={endpointKeyword}
            onKeywordChange={handleKeywordChange}
            selectedTags={endpointTags}
            onSelectedTagsChange={handleTagsChange}
            tagsMode={endpointTagsMode}
            onTagsModeChange={handleTagsModeChange}
            page={endpointPage}
            onPageChange={setEndpointPage}
            onAdd={() => {
              setEditingEndpoint(null);
              setEndpointDialogOpen(true);
            }}
            onEdit={(endpoint) => {
              setEditingEndpoint(endpoint);
              setEndpointDialogOpen(true);
            }}
            onDelete={(endpoint) => deleteEndpoint.mutate(endpoint.id)}
          />
        </TabsContent>

        <TabsContent value="environments" className="space-y-4">
          <EnvironmentsTab
            spaceId={spaceId}
            onAdd={() => {
              setEditingEnv(null);
              setEnvDialogOpen(true);
            }}
            onEdit={(env) => {
              setEditingEnv(env);
              setEnvDialogOpen(true);
            }}
            onDelete={(env) => deleteEnvironment.mutate(env.id)}
          />
        </TabsContent>

        <TabsContent value="memories" className="space-y-4">
          <MemoriesTab spaceId={spaceId} />
        </TabsContent>

        <TabsContent value="knowledge" className="space-y-4">
          <KnowledgeTab spaceId={spaceId} />
        </TabsContent>

        <TabsContent value="agent-runs" className="space-y-4">
          <AgentRunsTab
            spaceId={spaceId}
            page={agentRunPage}
            onPageChange={setAgentRunPage}
          />
        </TabsContent>
      </Tabs>

      <EndpointFormDialog
        open={endpointDialogOpen}
        onOpenChange={setEndpointDialogOpen}
        spaceId={spaceId}
        endpoint={editingEndpoint}
      />

      <EnvironmentFormDialog
        open={envDialogOpen}
        onOpenChange={setEnvDialogOpen}
        spaceId={spaceId}
        environment={editingEnv}
      />
    </div>
  );
}
