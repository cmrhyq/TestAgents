import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { MessageSquare } from "lucide-react";

import { useSpace } from "@/hooks/use-spaces.ts";
import { useEndpoints, useDeleteEndpoint } from "@/hooks/use-endpoints.ts";
import { useEnvironments, useDeleteEnvironment } from "@/hooks/use-environments.ts";
import { useAgentRuns } from "@/hooks/use-agent-runs.ts";
import { useDebouncedValue } from "@/hooks/use-debounced-value.ts";
import { Card, CardContent } from "@/components/ui/card.tsx";
import { Button } from "@/components/ui/button.tsx";
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

const PAGE_SIZE = 10;

/** 空间详情页：概览、会话、接口、环境、记忆、知识库与执行记录。 */
export default function SpaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const spaceId = id || "";

  const { data: space, isLoading: spaceLoading } = useSpace(spaceId);

  const [endpointPage, setEndpointPage] = useState(1);
  const [agentRunPage, setAgentRunPage] = useState(1);
  const [endpointKeyword, setEndpointKeyword] = useState("");
  const debouncedEndpointKeyword = useDebouncedValue(endpointKeyword, 300);

  useEffect(() => {
    setEndpointPage(1);
  }, [debouncedEndpointKeyword]);

  const {
    data: endpointsData,
    isLoading: endpointsLoading,
    isError: endpointsError,
    refetch: refetchEndpoints,
  } = useEndpoints({
    space_id: spaceId,
    keyword: debouncedEndpointKeyword || undefined,
    page: endpointPage,
    page_size: PAGE_SIZE,
  });
  const {
    data: environmentsData,
    isLoading: environmentsLoading,
    isError: environmentsError,
    refetch: refetchEnvironments,
  } = useEnvironments({
    space_id: spaceId,
  });
  const {
    data: agentRunsData,
    isLoading: agentRunsLoading,
    isError: agentRunsError,
    refetch: refetchAgentRuns,
  } = useAgentRuns({
    space_id: spaceId,
    page: agentRunPage,
    page_size: PAGE_SIZE,
  });

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
    <div className="space-y-6">
      <Card className="bg-surface-primary/50">
        <CardContent className="pt-6">
          <div className="flex items-start justify-between">
            <div className="min-w-0">
              <div className="annotation mb-1.5 text-primary">SPACE_{space.id}</div>
              <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
                {space.name}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <Badge variant={space.status === 1 ? "success" : "secondary"}>
                  {SPACE_STATUS_MAP[space.status] ?? "未知"}
                </Badge>
              </div>
              {space.description && (
                <p className="mt-2 text-sm text-muted-foreground">{space.description}</p>
              )}
            </div>

            <Button asChild size="sm">
              <Link to={`/chat?space_id=${space.id}`}>
                <MessageSquare className="mr-2 h-3.5 w-3.5" />
                开始对话
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

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
            onKeywordChange={setEndpointKeyword}
            data={endpointsData?.items ?? []}
            total={endpointsData?.total ?? 0}
            loading={endpointsLoading}
            error={endpointsError}
            onRetry={() => refetchEndpoints()}
            page={endpointPage}
            pageSize={PAGE_SIZE}
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
            data={environmentsData?.items ?? []}
            loading={environmentsLoading}
            error={environmentsError}
            onRetry={() => refetchEnvironments()}
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
            data={agentRunsData?.items ?? []}
            total={agentRunsData?.total ?? 0}
            loading={agentRunsLoading}
            error={agentRunsError}
            onRetry={() => refetchAgentRuns()}
            page={agentRunPage}
            pageSize={PAGE_SIZE}
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
