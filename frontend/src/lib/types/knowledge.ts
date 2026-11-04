import type { Id } from "./common";

/** 文档索引状态。 */
export type DocumentStatus = "pending" | "indexed" | "failed";
/** 索引方式：向量检索，或降级到 SQLite LIKE 的词法检索。 */
export type IndexMode = "vector" | "lexical";

/** 知识库文档的索引信息。 */
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

/** 文档列表响应。 */
export interface DocumentListResponse {
  items: KnowledgeDocument[];
  total: number;
  /** 服务端是否启用了向量检索；为 false 时前端提示「词法检索」 */
  vector_enabled: boolean;
}

/** 文档切片。 */
export interface KnowledgeChunk {
  id: Id;
  seq: number;
  content: string;
}

/** 检索命中项，字段名对齐后端 `SearchHit.to_dict()`。 */
export interface SearchHit {
  /** 来源文档名 */
  document: string;
  /** 切片在文档中的序号 */
  seq: number;
  content: string;
  score: number;
}

/** 检索结果。 */
export interface SearchResponse {
  query: string;
  vector_enabled: boolean;
  hits: SearchHit[];
}

/** 工作目录节点。 */
export interface WorkspaceNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size: number;
  children?: WorkspaceNode[];
}

/** 工作目录树响应。 */
export interface WorkspaceTreeResponse {
  space_id: Id;
  root: string;
  nodes: WorkspaceNode[];
}
