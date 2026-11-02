type ResourceId = string | number;

function createResourceKeys<const TPrefix extends string>(prefix: TPrefix) {
  return {
    all: [prefix] as const,
    list: (params?: unknown) => [prefix, "list", params] as const,
    detail: (id: ResourceId) => [prefix, "detail", id] as const,
  };
}

export const queryKeys = {
  spaces: createResourceKeys("spaces"),
  endpoints: createResourceKeys("endpoints"),
  environments: createResourceKeys("environments"),
  agentRuns: {
    ...createResourceKeys("agent-runs"),
    toolCalls: (runId: ResourceId, includeBody: boolean) =>
      ["agent-runs", "tool-calls", runId, includeBody] as const,
  },
  reports: createResourceKeys("reports"),
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

export type ResourceQueryKeys = ReturnType<typeof createResourceKeys>;
