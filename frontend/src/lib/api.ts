// Frontend API Client for AI Lead Intelligence Platform (Multi-Tenant SaaS)

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// -------------------------------------------------------------
// Authentication & Organization Types
// -------------------------------------------------------------

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
  organization: OrganizationResponse;
}

export interface CurrentUserResponse {
  user: UserResponse;
  organization: OrganizationResponse;
  organizations: OrganizationResponse[];
}

export interface UserRegisterRequest {
  email: string;
  password: string;
  full_name: string;
  organization_name?: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
}

// -------------------------------------------------------------
// Campaign Types
// -------------------------------------------------------------

export interface CampaignICPConfig {
  industries?: string[];
  geographies?: string[];
  company_sizes?: string[];
  business_models?: string[];
  technologies?: string[];
  target_titles?: string[];
  minimum_score?: number;
}

export interface CampaignCreateRequest {
  name: string;
  description?: string;
  icp?: Record<string, any>;
}

export interface CampaignUpdateRequest {
  name?: string;
  description?: string;
  status?: "ACTIVE" | "PAUSED" | "ARCHIVED";
  icp?: Record<string, any>;
}

export interface CampaignResponse {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  status: "ACTIVE" | "PAUSED" | "ARCHIVED";
  icp_config: Record<string, any>;
  total_leads: number;
  qualified_leads: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: CampaignResponse[];
  total: number;
}

// -------------------------------------------------------------
// Analytics Types
// -------------------------------------------------------------

export interface AnalyticsOverviewResponse {
  total_leads: number;
  qualified_leads: number;
  qualification_rate: number;
  total_crawls: number;
  pages_crawled: number;
  jobs_completed: number;
  jobs_failed: number;
  estimated_ai_cost: number;
}

export interface DailyUsageItem {
  date: string;
  crawls: number;
  pages_crawled: number;
  leads_created: number;
  ai_qualifications: number;
  embeddings_generated: number;
  jobs_completed: number;
  jobs_failed: number;
  estimated_ai_cost: number;
}

export interface AnalyticsUsageResponse {
  items: DailyUsageItem[];
}

export interface CampaignLeadStat {
  campaign_id?: string | null;
  campaign_name: string;
  total_leads: number;
  avg_icp_score: number;
}

export interface IndustryLeadStat {
  industry: string;
  count: number;
}

export interface AnalyticsLeadsResponse {
  total_leads: number;
  by_campaign: CampaignLeadStat[];
  by_industry: IndustryLeadStat[];
  by_status: Record<string, number>;
}

// -------------------------------------------------------------
// Lead & Search Types
// -------------------------------------------------------------

export interface LeadListItem {
  lead_id: string;
  crawl_target_id: string;
  campaign_id?: string | null;
  company_name: string;
  domain: string;
  industry: string;
  company_summary: string;
  value_proposition: string;
  icp_score: number;
  confidence_score: number;
  geography: string;
  estimated_company_size: string;
  status: string;
  created_at: string;
  similarity?: number | null;
}

export interface LeadListResponse {
  items: LeadListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface SignalItem {
  id: string;
  signal: string;
  evidence: string;
  source_url?: string | null;
  sentiment: string;
  created_at: string;
}

export interface SourcePageItem {
  id: string;
  url: string;
  final_url: string;
  title?: string | null;
  depth: number;
  status_code: number;
  fetched_at: string;
}

export interface AuditLogItem {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  request_id?: string | null;
  created_at: string;
}

export interface EmbeddingMetadata {
  id: string;
  content_hash: string;
  dimension: number;
  indexed_hnsw: boolean;
  created_at: string;
}

export interface LeadDetail {
  id: string;
  crawl_target_id: string;
  campaign_id?: string | null;
  company_name: string;
  domain: string;
  company_summary: string;
  value_proposition: string;
  industry: string;
  target_audience: string;
  business_model: string;
  geography: string;
  estimated_company_size: string;
  technology_signals: string[];
  icp_score: number;
  confidence_score: number;
  status: string;
  qualification_reasoning: string;
  qualification_json: Record<string, any>;
  positive_signals: string[];
  negative_signals: string[];
  created_at: string;
  updated_at: string;
  signals: SignalItem[];
  source_pages: SourcePageItem[];
  embedding?: EmbeddingMetadata | null;
  audit_logs: AuditLogItem[];
}

export interface FilterParams {
  page?: number;
  page_size?: number;
  search?: string;
  campaign_id?: string;
  min_icp_score?: number;
  max_icp_score?: number;
  industry?: string;
  geography?: string;
  status?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface SemanticSearchResultItem {
  lead_id: string;
  company_name: string;
  domain: string;
  industry: string;
  company_summary: string;
  icp_score: number;
  confidence_score: number;
  geography: string;
  status: string;
  similarity: number;
}

export interface SemanticSearchResponse {
  query: string;
  count: number;
  results: SemanticSearchResultItem[];
}

export interface HybridSearchResponse {
  query: string;
  keyword_count: number;
  semantic_count: number;
  total_unique: number;
  results: SemanticSearchResultItem[];
}

export interface JobEnqueueResponse {
  job_id: string;
  job_type: string;
  status: string;
  message: string;
  reused: boolean;
}

export interface JobStatusResponse {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  current_stage: string;
  pages_discovered: number;
  pages_crawled: number;
  crawl_target_id?: string | null;
  lead_id?: string | null;
  error_message?: string | null;
  retry_count: number;
  payload: Record<string, any>;
  result: Record<string, any>;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

// -------------------------------------------------------------
// Auth & Organization Storage Helpers
// -------------------------------------------------------------

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("leadintel_token");
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("leadintel_token", token);
  } else {
    localStorage.removeItem("leadintel_token");
  }
}

export function getActiveOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("leadintel_active_org_id");
}

export function setActiveOrgId(orgId: string | null): void {
  if (typeof window === "undefined") return;
  if (orgId) {
    localStorage.setItem("leadintel_active_org_id", orgId);
  } else {
    localStorage.removeItem("leadintel_active_org_id");
  }
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {});
  
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const activeOrgId = getActiveOrgId();
  if (activeOrgId && !headers.has("X-Organization-Id")) {
    headers.set("X-Organization-Id", activeOrgId);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}

// -------------------------------------------------------------
// Auth API Endpoints
// -------------------------------------------------------------

export async function registerUser(req: UserRegisterRequest): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Registration failed (HTTP ${res.status})`);
  }
  const data: TokenResponse = await res.json();
  setAuthToken(data.access_token);
  setActiveOrgId(data.organization.id);
  return data;
}

export async function loginUser(req: UserLoginRequest): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Login failed (HTTP ${res.status})`);
  }
  const data: TokenResponse = await res.json();
  setAuthToken(data.access_token);
  setActiveOrgId(data.organization.id);
  return data;
}

export async function logoutUser(): Promise<void> {
  try {
    await fetchWithAuth(`${API_BASE}/api/v1/auth/logout`, { method: "POST" });
  } catch {
    // Ignore network error on logout
  } finally {
    setAuthToken(null);
    setActiveOrgId(null);
  }
}

export async function fetchMe(): Promise<CurrentUserResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/auth/me`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch profile (HTTP ${res.status})`);
  }
  return res.json();
}

// -------------------------------------------------------------
// Campaign API Endpoints
// -------------------------------------------------------------

export async function fetchCampaigns(): Promise<CampaignListResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/campaigns`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch campaigns (HTTP ${res.status})`);
  }
  return res.json();
}

export async function createCampaign(req: CampaignCreateRequest): Promise<CampaignResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/campaigns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to create campaign (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchCampaign(id: string): Promise<CampaignResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/campaigns/${id}`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch campaign (HTTP ${res.status})`);
  }
  return res.json();
}

export async function updateCampaign(id: string, req: CampaignUpdateRequest): Promise<CampaignResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/campaigns/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update campaign (HTTP ${res.status})`);
  }
  return res.json();
}

export async function deleteCampaign(id: string): Promise<void> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/campaigns/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to delete campaign (HTTP ${res.status})`);
  }
}

// -------------------------------------------------------------
// Analytics API Endpoints
// -------------------------------------------------------------

export async function fetchAnalyticsOverview(): Promise<AnalyticsOverviewResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/analytics/overview`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch analytics overview (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchAnalyticsUsage(): Promise<AnalyticsUsageResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/analytics/usage`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch usage metrics (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchAnalyticsLeads(): Promise<AnalyticsLeadsResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/analytics/leads`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch lead analytics (HTTP ${res.status})`);
  }
  return res.json();
}

// -------------------------------------------------------------
// Lead & Search API Endpoints
// -------------------------------------------------------------

export async function fetchLeads(params: FilterParams = {}): Promise<LeadListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", params.page.toString());
  if (params.page_size) query.set("page_size", params.page_size.toString());
  if (params.search) query.set("search", params.search);
  if (params.campaign_id) query.set("campaign_id", params.campaign_id);
  if (params.min_icp_score !== undefined) query.set("min_icp_score", params.min_icp_score.toString());
  if (params.max_icp_score !== undefined) query.set("max_icp_score", params.max_icp_score.toString());
  if (params.industry) query.set("industry", params.industry);
  if (params.geography) query.set("geography", params.geography);
  if (params.status) query.set("status", params.status);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);

  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads?${query.toString()}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch leads (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchLeadDetail(leadId: string): Promise<LeadDetail> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads/${leadId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Lead not found (HTTP ${res.status})`);
  }
  return res.json();
}

export async function updateLeadStatus(leadId: string, status: string): Promise<{ id: string; status: string; message: string }> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads/${leadId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update status (HTTP ${res.status})`);
  }
  return res.json();
}

export async function semanticSearch(query: string, limit: number = 20): Promise<SemanticSearchResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Semantic search failed (HTTP ${res.status})`);
  }
  return res.json();
}

export async function hybridSearch(query: string, limit: number = 20): Promise<HybridSearchResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads/search/hybrid`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Hybrid search failed (HTTP ${res.status})`);
  }
  return res.json();
}

export async function seedDemoData(): Promise<{ message: string; targets_seeded: number; leads_seeded: number }> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/leads/seed-demo`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Seeding failed (HTTP ${res.status})`);
  }
  return res.json();
}

export function getExportUrl(format: "csv" | "json", params: FilterParams = {}): string {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.campaign_id) query.set("campaign_id", params.campaign_id);
  if (params.min_icp_score !== undefined) query.set("min_icp_score", params.min_icp_score.toString());
  if (params.max_icp_score !== undefined) query.set("max_icp_score", params.max_icp_score.toString());
  if (params.industry) query.set("industry", params.industry);
  if (params.geography) query.set("geography", params.geography);
  if (params.status) query.set("status", params.status);
  
  const token = getAuthToken();
  if (token) query.set("token", token);
  const activeOrgId = getActiveOrgId();
  if (activeOrgId) query.set("org_id", activeOrgId);

  return `${API_BASE}/api/v1/leads/export.${format}?${query.toString()}`;
}

// -------------------------------------------------------------
// Asynchronous Job API Endpoints
// -------------------------------------------------------------

export async function enqueueCrawlJob(
  url: string,
  maxPages: number = 6,
  force: boolean = false,
  campaignId?: string
): Promise<JobEnqueueResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/jobs/crawl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, max_pages: maxPages, force, campaign_id: campaignId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to enqueue crawl job (HTTP ${res.status})`);
  }
  return res.json();
}

export async function enqueuePipelineJob(
  url: string,
  maxPages: number = 6,
  icpProfile?: Record<string, any>,
  force: boolean = false,
  campaignId?: string
): Promise<JobEnqueueResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/jobs/pipeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      max_pages: maxPages,
      icp_profile: icpProfile,
      force,
      campaign_id: campaignId,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to enqueue pipeline job (HTTP ${res.status})`);
  }
  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Job not found (HTTP ${res.status})`);
  }
  return res.json();
}

export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string; message: string }> {
  const res = await fetchWithAuth(`${API_BASE}/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to cancel job (HTTP ${res.status})`);
  }
  return res.json();
}

export function getJobEventsUrl(jobId: string): string {
  const token = getAuthToken();
  const orgId = getActiveOrgId();
  const query = new URLSearchParams();
  if (token) query.set("token", token);
  if (orgId) query.set("org_id", orgId);
  const qStr = query.toString();
  return `${API_BASE}/api/v1/jobs/${jobId}/events${qStr ? `?${qStr}` : ""}`;
}
