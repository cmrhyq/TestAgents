import type { Id } from "./common";

/** 文档索引状态。 */
export type DocumentStatus = "pending" | "indexed" | "failed";
/** 索引方式：向量（Chroma 可用）或词法（降级到 SQLite LIKE）。 */
export type IndexMode = "vector" | "lexical";

export interface KnowledgeDocument {
  id: Id;
  space_id: Id;
  filename: string;
  file_path: string;
  mime: string;
  size: number;
  chunk_count: number;
  status: DocumentStatus | string;
  index_mode: IndexMode | string;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: KnowledgeDocument[];
  total: number;
  /** 服务端是否启用了向量检索；为 false 时前端提示「词法检索」 */
  vector_enabled: boolean;
}

export interface KnowledgeChunk {
  id: Id;
  seq: number;
  content: string;
}

/** 检索命中项。字段名对齐后端 ``SearchHit.to_dict()``。 */
export interface SearchHit {
  /** 来源文档名 */
  document: string;
  /** 切片在文档中的序号 */
  seq: number;
  content: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  vector_enabled: boolean;
  hits: SearchHit[];
}

/** 工作目录节点（「概览」页展示空间沙箱内容）。 */
export interface WorkspaceNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size: number;
  children?: WorkspaceNode[];
}

export interface WorkspaceTreeResponse {
  space_id: Id;
  root: string;
  nodes: WorkspaceNode[];
}
