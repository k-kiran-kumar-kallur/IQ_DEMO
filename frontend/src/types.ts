export type Query = {
  lang: "cypher" | "sql" | "llm";
  label: string;
  text: string;
  params: Record<string, unknown>;
  rows: number;
  ms: number;
  sample: Record<string, unknown>[];
};

export type Step = {
  agent: string;
  title: string;
  status: "ran" | "skipped" | "error";
  reason: string;
  summary: string;
  queries: Query[];
  items: Record<string, unknown>[];
  notes: string[];
  data: Record<string, unknown>;
  start_ms: number;
  ms: number;
};

export type Evidence = {
  cid: string;
  kind: "document" | "graph" | "fact";
  title: string;
  section?: string;
  source_path: string;
  sources?: string[];
  raw_path?: string;
  sheet?: string;
  iq: string;
  classification?: string;
  text: string;
  why: string[];
  score?: number;
  rows?: number;
  sql?: string;
};

export type PathNode = { agent: string; status: string; ms: number; summary: string; reason: string };

export type GNode = { id: string; label: string; name?: string; root?: boolean };
export type GEdge = { source: string; target: string; type: string };

export type Result = {
  id: number;
  question: string;
  user: string;
  user_name: string;
  asked_at: string;
  answer: string;
  status: string;
  verification: { status: string; cited: string[]; invalid: string[]; numbers_checked: number; unsupported: string[] };
  total_ms: number;
  llm: { provider?: string; model?: string; ms?: number; input_tokens?: number; output_tokens?: number };
  evidence: Evidence[];
  steps: Step[];
  path: PathNode[];
  subgraph: { nodes?: GNode[]; edges?: GEdge[]; paths?: string[] };
  entities: { id: string; label: string; name: string }[];
};

export type Me = {
  username: string;
  display_name: string;
  title: string;
  role: string;
  role_name: string;
  note: string;
  is_admin: boolean;
  accounts: string[];
  partners: string[];
  account_names: string[];
  partner_names: string[];
  grants: Record<string, string>;
  active?: boolean;
  last_login?: string | null;
};

export type DemoUser = {
  username: string;
  display_name: string;
  title: string;
  role_name: string;
  note: string;
  accounts: string[];
  partners: string[];
  account_names: string[];
  partner_names: string[];
};

export type LoginAudit = { id: number; at: string; username: string; success: number; reason: string; ip: string };

export type HistoryRow = { id: number; asked_at: string; user: string; question: string; status: string; total_ms: number };

export type SettingField = { value: string; is_set: boolean; secret: boolean; source: string; env: string };

export type Status = {
  neo4j: { ok: boolean; error?: string; nodes?: number; docs?: number; chunks?: number; server?: { version?: string; edition?: string } };
  llm: { provider: string; model: string; configured: boolean };
  documents: number;
  tables: number;
  embed_model: string;
  last_ingest: { status: string; finished_at: string; chunks: number } | null;
};

export type IngestState = {
  running: boolean;
  phase: string;
  done: number;
  total: number;
  message: string;
  counts: Record<string, number>;
  log: string[];
};
