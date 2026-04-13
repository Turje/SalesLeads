export type CompanyType = "CRE_OPERATOR" | "COWORKING" | "MULTI_TENANT" | "OTHER";
export type PipelineStage = "NEW" | "APPROVED" | "CONTACTED" | "MEETING" | "PROPOSAL" | "CLOSED" | "DISAPPROVED";

export interface Lead {
  id: number;
  company_name: string;
  company_type: CompanyType;
  contact_name: string;
  contact_title: string;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  website: string | null;
  address: string;
  building_type: string;
  sqft: number | null;
  num_tenants: number | null;
  borough: string;
  neighborhood: string;
  year_built: number | null;
  floors: number | null;
  num_employees: number | null;
  building_isp: string | null;
  available_isps: string[];
  equipment: Record<string, string>;
  building_summary: string;
  current_it_provider: string | null;
  tech_signals: string[];
  recent_news: string[];
  social_links: Record<string, string>;
  sources: string[];
  discovery_date: string;
  score: number;
  qualification_notes: string;
  pipeline_stage: PipelineStage;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface PipelineOverview {
  stages: Record<string, number>;
  total: number;
  last_run: Record<string, unknown> | null;
}

export interface AgentStatus {
  total_leads: number;
  last_run: Record<string, unknown> | null;
  stage_counts: Record<string, number>;
}

export interface EmailDraftRequest {
  lead_id: number;
  template: "initial_outreach" | "follow_up" | "meeting_request";
}

export interface EmailDraftResponse {
  subject: string;
  body: string;
  model: string;
  duration_ms: number;
}
