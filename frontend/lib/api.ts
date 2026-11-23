import { createClient } from "@/lib/supabase/client";
 
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
 
export type JobStatus = "queued" | "running" | "done" | "empty" | "error" | "cancelled";
 
export interface PlazaRow {
    name: string;
    state: string;
    county: string;
    city: string;
    address: string;
    num_anchors: number;
    anchor_names: string;
    num_tenants: number;
    tenant_names: string;
    score: number | string;
    brokerages: string;
    brokers: string;
    broker_contacts: string;
    broker_urls: string;
}
 
export interface JobSummary {
    id: string;
    city: string;
    status: JobStatus;
    created_at: number;
    plaza_count?: number | null;
}
 
export interface JobDetail extends JobSummary {
    log: string[];
    error?: string | null;
    reason?: string | null;
    display?: string | null;
    plazas?: PlazaRow[] | null;
    map_available: boolean;
    excel_available: boolean;
    map_url?: string | null;
}
 
export interface HistoryRun {
    id: string;
    city: string;
    display: string;
    ran_at: string;
    radius_km: number;
    map_url: string | null;
    plaza_count: number;
    excel_available: boolean;
}
 
export interface HistoryDetail extends HistoryRun {
    plazas: PlazaRow[];
}
 
export interface UserProfile {
    id: string;
    email: string;
    role: string;
    created_at: string;
    first_name?: string | null;
    last_name?: string | null;
    avatar_url?: string | null;
}
 
export interface RingProfile {
    population: number;
    daytime_population: number;
    median_age: number | null;
    white_pct: number | null;
    black_pct: number | null;
    hispanic_pct: number | null;
    asian_pct: number | null;
    employee_count: number;
    white_collar_pct: number | null;
    blue_collar_pct: number | null;
    median_hh_income: number | null;
    hh_discretionary_spend: number | null;
    hh_dining_spend: number | null;
    n_block_groups: number;
}
 
export interface DemographicsResponse {
    address: string;
    lat: number;
    lon: number;
    renter_pct: number | null;
    wfh_pct: number | null;
    rings: Record<string, RingProfile>;
}
 
export interface SitePresentationBrand {
    code: string;
    label: string;
}
 
export interface SitePresentationPreview {
    blob: Blob;
    filename: string;
}
 
export interface DigestListing {
    id:string;
 
    kind: "space" | "legacy";
    brokerage?: string | null;
    agent_name?: string | null;
    phone?: string | null;
    email?: string | null;
    listing_url?: string | null;
    flyer_url?: string | null;
    photo_url?: string | null;
    source?: string | null;
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    deactivated_at?: string | null;
 
    suite?: string | null;
    listing_type?: string | null;
    space_type?: string | null;
    sf_min?: number | null;
    sf_max?: number | null;
    rate_min?: number | null;
    rate_max?: number | null;
    rate_unit?: string | null;
    available_now?: boolean | null;
}
 
export interface DigestPlaza {
    id:string;
    name:string;
    city:string;
    state:string;
    county?: string | null;
    address?: string | null;
    lat?: number | null;
    lng?: number | null;
    anchor_names?: string | null;
    num_anchors: number;
    num_tenants: number;
    score?: number | null;
    property_type?: string | null;
    nearest_brand_store?: string | null;
    nearest_brand_store_mi?: number | null;
    listings: DigestListing[];
}
 
export interface DigestResponse {
    window_start: string;
    generated_at: string;
    last_run_at?: string | null;
    run_is_stale: boolean;
    brand?: string | null;
    brand_label?: string | null;
    brand_store_count: number;
    brand_overlap_mi: number;
    new_listing_count: number;
    new_total: number;
    new_truncated: boolean;
    removed_listing_count: number;
    active_listing_count?: number | null;
    active_space_count?: number | null;
    active_legacy_count?: number | null;
    removed_tracking_enabled: boolean;
    new: DigestPlaza[];
    removed: DigestPlaza[];
}
 
export interface InventoryItem extends DigestListing {
    group_id: string;
    name: string;
    address?: string | null;
    city?: string | null;
    state?: string | null;
    county?: string | null;
    lat?: number | null;
    lng?: number | null;
    property_type?: string | null;
    anchor_names?: string | null;
    num_anchors: number;
    num_tenants: number;
    score?: number | null;
    nearest_brand_store?: string | null;
    nearest_brand_store_mi?: number | null;
}
 
export interface InventoryResponse {
    items: InventoryItem[];
    total: number;
    limit: number;
    offset: number;
    brand?: string | null;
    brand_label?: string | null;
    brand_store_count: number;
    brand_overlap_mi: number;
}
 
export interface InventoryQuery {
    q?: string;
    state?: string;
    city?: string;
    kind?: "space" | "legacy" | "";
    space_type?: string;
    listing_type?: string;
    min_sf?: number | null;
    max_sf?: number | null;
    has_photo?: boolean;
    has_flyer?: boolean;
    sort?: string;
    brand?: string | null;
    limit?: number;
    offset?: number;
}
 
async function authHeaders(): Promise<HeadersInit> {
    const supabase = createClient();
    const {
        data: { session },
    } = await supabase.auth.getSession();
    if (!session) {
        throw new Error("Not signed in");
    }
    return { Authorization: `Bearer ${session.access_token}` };
}
 
async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = { ...(await authHeaders()), ...(init.headers || {}) };
    const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
 
    if (res.status === 401) {
        // Session expired/invalid server-side -- send back through the login gate.
        window.location.href = "/login";
        throw new Error("Session expired");
    }
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Request failed (${res.status})`);
    }
    return res;
}
 
async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await apiFetch(path, init);
    return res.json() as Promise<T>;
}
 
 
 
 
async function downloadFile(path: string, fallbackName: string): Promise<void> {
    const res = await apiFetch(path);
    await _saveBlob(res, fallbackName);
}
 
async function downloadFilePost(path: string, body: unknown, fallbackName: string): Promise<void> {
    const res = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    await _saveBlob(res, fallbackName);
}
 
async function _saveBlob(res: Response, fallbackName: string): Promise<void> {
    const { blob, filename } = await _readBlob(res, fallbackName);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}
 
async function _readBlob(res: Response, fallbackName: string): Promise<SitePresentationPreview> {
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    return { blob, filename: match?.[1] || fallbackName };
}
 
// Like downloadFilePost, but returns the blob instead of triggering a
// browser download -- used for the Site Presentations preview, where the
// file needs to be loaded into an in-page editor first.
async function fetchBlobPost(
    path: string,
    body: unknown,
    fallbackName: string,
    signal?: AbortSignal
): Promise<SitePresentationPreview> {
    const res = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
    });
    return _readBlob(res, fallbackName);
}
 
// ---- Saved projections (per brand) ----------------------------------------
// Only sanitized projections ever reach the browser: ranges, a score and driver
// shares. The sales data and the model stay in the private TGG service.

export type ProjectionInputValue = string | boolean;
export type ProjectionInputs = Record<string, ProjectionInputValue>;

 
export interface ProjectionField {
    id: string;
    type: "select" | "bool";
    label: string;
    options?: string[];
    default: ProjectionInputValue;
}

export interface ProjectionBrand {
    id: string;
    label: string;
    fields: ProjectionField[];
}
 
export interface ProjectionInterval {
    weekly: [number, number];
    annual: [number, number];
}
 
export interface ProjectionDriver {
    label: string;
    direction: "up" | "down";
    share_pct: number;
}
 
export interface ProjectionMapPoint {
    brand: string;
    cat: string;
    lat: number;
    lon: number;
    mi: number;
    revenue: string;
    rank: string;
}

export interface ProjectionMapRing { mi: number; color: string; label: string }
export interface ProjectionMapCat { id: string; label: string; color: string }
 
export interface ProjectionMap {
    radius_mi: number;
    points: ProjectionMapPoint[];

    rings?: ProjectionMapRing[];
    cats?: ProjectionMapCat[];
    cava_radius_mi?: number;
    anchor_radius_mi?: number;
}

export interface ProjectionRange {
    id: string;
    label: string;
    weekly: [number, number];
    annual: [number, number];
    headline: boolean;
}
 

export interface TggResult {
    brand_kind?: "tgg";
    matched_address: string;
    lat: number;
    lon: number;
    format: string;
    corporate: boolean;
    score: number;
    score_within_type: number;
    top10_pct: number;
    intervals: Record<string, ProjectionInterval>;
    drivers: ProjectionDriver[];
    flags: string[];
    model_r2: number;
    nearby?: Record<string, string | number | null>;
    map?: ProjectionMap | null;
}


export interface SourdoughResult {
    brand_kind: "sourdough";
    matched_address: string;
    lat: number;
    lon: number;
    state?: string | null;
    mall: boolean;
    market: string;
    n_market_stores: number;
    new_market: boolean;
    ranges: ProjectionRange[];
    score: number;
    score_market?: number | null;
    chance?: { label: string, pct: number } | null;
    chance_low?: { label: string, pct: number } | null;
    held_out?: { holds_pct: number; r2: number | null } | null;
    notes: string[];
    facts: { label: string; value: string }[];
    map?: ProjectionMap | null;
}

export type ProjectionResult = TggResult | SourdoughResult;
 
export type ProjectionStatus = "pending" | "running" | "done" | "error";
 
export interface ProjectionSave {
    id: string;
    brand: string;
    address_key: string;
    address: string;
    name?: string | null;
    city?: string | null;
    state?: string | null;
    source: "digest" | "manual";
    inputs: ProjectionInputs;
    status: ProjectionStatus;
    error?: string | null;
    result?: ProjectionResult | null;
    saved_by_email?: string | null;
    created_at: string;
    updated_at: string;
}
 
export interface ProjectionList {
    brand: string;
    label: string;
    fields: ProjectionField[];
    saves: ProjectionSave[];
}
 
export interface ProjectionMarkBody {
    key: string;
    address: string;
    name?: string | null;
    city?: string | null;
    state?: string | null;
    source: "digest" | "manual";
    brands: string[];
    inputs?: Record<string, ProjectionInputs>;
}
 
export const api = {
    projectionAccess: () => apiJson<{ brands: ProjectionBrand[] }>("/api/projections/access"),
 
    projectionMarks: () => apiJson<{ marks: Record<string, string[]> }>("/api/projections/marks"),
 
    putProjectionMark: (body: ProjectionMarkBody) =>
        apiJson<{ key: string; brands: string[]; saves: ProjectionSave[] }>("/api/projections/mark", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }),
 
    listProjections: (brand: string) =>
        apiJson<ProjectionList>(`/api/projections?brand=${encodeURIComponent(brand)}`),
 
    rerunProjection: (id: string, body: { inputs?: ProjectionInputs }) =>
        apiJson<ProjectionSave>(`/api/projections/${id}/rerun`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }),
 
    deleteProjection: (id: string) =>
        apiJson<{ ok: boolean }>(`/api/projections/${id}`, { method: "DELETE" }),
 
    getDigest: (days: number, brand?: string | null) => {
        const params = new URLSearchParams({ days: String(days) });
        if (brand) params.set("brand", brand);
        return apiJson<DigestResponse>(`/api/digest?${params.toString()}`);
    },
 
    getInventory: (query: InventoryQuery, signal?: AbortSignal) => {
        const params = new URLSearchParams();
        (Object.entries(query) as [string, unknown][]).forEach(([k,v]) => {
            if (v === undefined || v === null || v === "" || v === false) return;
            params.set(k,String(v));
        });
        return apiJson<InventoryResponse>(`/api/inventory?${params.toString()}`, { signal });
    },
 
    defaults: () => apiJson<{ search_km: number }>("/api/defaults"),
 
    listSearches: () => apiJson<JobSummary[]>("/api/searches"),
 
    getSearch: (id: string) => apiJson<JobDetail>(`/api/searches/${id}`),
 
    createSearch: (city: string, searchKm: number, rescrapeAfterDays: number | null) =>
        apiJson<JobSummary>("/api/searches", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                city,
                search_km: searchKm,
                rescrape_after_days: rescrapeAfterDays,
            }),
        }),
 
    deleteSearch: (id: string) => apiFetch(`/api/searches/${id}`, { method: "DELETE" }),
 
    cancelSearch: (id: string) => apiFetch(`/api/searches/${id}/cancel`, { method: "POST" }),
 

    getMapHtml: (id: string) => apiFetch(`/api/searches/${id}/map`).then((r) => r.text()),
 
    downloadExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/searches/${id}/excel`, `${cityLabel}.xlsx`),
 
    listHistory: () => apiJson<HistoryRun[]>("/api/history"),
 
    getHistoryRun: (id: string) => apiJson<HistoryDetail>(`/api/history/${id}`),
 
    downloadHistoryExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/history/${id}/excel`, `${cityLabel}.xlsx`),
 
    getMe: () => apiJson<UserProfile>("/api/me"),
 
    updateMe: (fields: { first_name?: string; last_name?: string }) =>
        apiJson<UserProfile>("/api/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(fields),
        }),
 
    uploadAvatar: (file: File) => {
        const formData = new FormData();
        formData.append("file", file);
        // No Content-Type header here -- letting fetch set the multipart
        // boundary itself. Setting it manually breaks the upload.
        return apiJson<UserProfile>("/api/me/avatar", {
            method: "POST",
            body: formData,
        });
    },
 
    listUsers: () => apiJson<UserProfile[]>("/api/users"),
 
    inviteUser: (email: string, role: string) =>
        apiJson<UserProfile>("/api/users/invite", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, role }),
        }),
 
    updateUserRole: (userId: string, role: string) =>
        apiJson<UserProfile>(`/api/users/${userId}/role`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role }),
        }),
 
    deleteOwnAccount: () => apiFetch("/api/users/me", { method: "DELETE" }),
 
    deleteUser: (userId: string) => apiFetch(`/api/users/${userId}`, { method: "DELETE" }),
 
    getDemographics: (address: string, radii: number[]) =>
        apiJson<DemographicsResponse>("/api/demographics", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ address, radii }),
        }),
 
    listSitePresentationBrands: () =>
        apiJson<SitePresentationBrand[]>("/api/site-presentations/brands"),
 
    previewSitePresentation: (
        brand: string, 
        address: string, 
        signal?: AbortSignal,
        coords?: {lat: number, lon: number}
    ) =>
        fetchBlobPost(
            "/api/site-presentations/generate",
            { brand, address, lat: coords?.lat, lon: coords?.lon },
            `${brand}_site_summary.xlsx`,
            signal
        ),
 
 
    exportSitePresentation: (filename: string, sheets: unknown[]) =>
        downloadFilePost(
            "/api/site-presentations/export",
            { filename, sheets },
            filename
        ),
};