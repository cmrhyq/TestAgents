type ResourceId = string | number;

function createResourceKeys<const TPrefix extends string>(prefix: TPrefix) {
  return {
    all: [prefix] as const,
    list: (params?: unknown) => [prefix, "list", params] as const,
    detail: (id: ResourceId) => [prefix, "detail", id] as const,
  };
}

/**
 * React Query 查询键注册表，按资源前缀集中管理。
 *
 * `all` 用于整资源缓存失效；`list` 与 `detail` 是 `createCrudHooks` 依赖的固定成员。
 */
export const queryKeys = {
  spaces: createResourceKeys("spaces"),
  endpoints: createResourceKeys("endpoints"),
  environments: createResourceKeys("environments"),
  agentRuns: {
    ...createResourceKeys("agent-runs"),
    toolCalls: (runId: ResourceId, includeBody: boolean) =>
      ["agent-runs", "tool-calls", runId, includeBody] as const,
  },
  reports: {
    ...createResourceKeys("reports"),
    /** 单条请求正文（详情页展开时按需拉） */
    request: (runId: ResourceId, requestId: ResourceId) =>
      ["reports", "request", runId, requestId] as const,
  },
  skills: createResourceKeys("skills"),
  conversations: {
    ...createResourceKeys("conversations"),
    messages: (id: ResourceId | null | undefined) => ["conversations", "messages", id] as const,
    bySpace: (spaceId: ResourceId | null | undefined) =>
      ["conversations", "space", spaceId] as const,
  },
  memories: {
    ...createResourceKeys("memories"),
    bySpace: (spaceId: ResourceId | null | undefined) => ["memories", "space", spaceId] as const,
  },
  knowledge: {
    all: ["knowledge"] as const,
    documents: (spaceId: ResourceId | null | undefined) =>
      ["knowledge", "documents", spaceId] as const,
    chunks: (documentId: ResourceId) => ["knowledge", "chunks", documentId] as const,
  },
  workspace: {
    tree: (spaceId: ResourceId | null | undefined) => ["workspace", "tree", spaceId] as const,
    agentsMd: (spaceId: ResourceId | null | undefined) =>
      ["workspace", "agents-md", spaceId] as const,
  },
};

/** 单个资源的查询键集合，供 `createCrudHooks` 使用。 */
export type ResourceQueryKeys = ReturnType<typeof createResourceKeys>;
