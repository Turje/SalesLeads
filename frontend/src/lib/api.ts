import type {
  Lead,
  LeadListResponse,
  PipelineOverview,
  AgentStatus,
  EmailDraftRequest,
  EmailDraftResponse,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  leads: {
    list: (params?: Record<string, string | number>) => {
      const search = new URLSearchParams();
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          if (v !== "" && v !== undefined && v !== null) search.set(k, String(v));
        });
      }
      return fetchJSON<LeadListResponse>(`${BASE}/leads?${search}`);
    },
    get: (id: number) => fetchJSON<Lead>(`${BASE}/leads/${id}`),
    updateStage: (id: number, stage: string) =>
      fetchJSON<Lead>(`${BASE}/leads/${id}/stage`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage }),
      }),
    updateNotes: (id: number, notes: string) =>
      fetchJSON<Lead>(`${BASE}/leads/${id}/notes`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes }),
      }),
    delete: (id: number) =>
      fetch(`${BASE}/leads/${id}`, { method: "DELETE" }),
  },
  pipeline: {
    overview: () => fetchJSON<PipelineOverview>(`${BASE}/pipeline/overview`),
    stage: (stage: string) =>
      fetchJSON<LeadListResponse>(`${BASE}/pipeline/stages/${stage}`).then(
        (r) => r.items
      ),
  },
  email: {
    draft: (req: EmailDraftRequest) =>
      fetchJSON<EmailDraftResponse>(`${BASE}/email/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      }),
  },
  export: {
    xlsx: async (stages?: string[], minScore?: number) => {
      const res = await fetch(`${BASE}/export/xlsx`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stages, min_score: minScore ?? 0 }),
      });
      if (!res.ok) throw new Error("Export failed");
      return res.blob();
    },
  },
  agents: {
    status: () => fetchJSON<AgentStatus>(`${BASE}/agents/status`),
    trigger: () =>
      fetchJSON<{ status: string }>(`${BASE}/agents/trigger`, { method: "POST" }),
  },
};
