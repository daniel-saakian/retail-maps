import { createClient } from "@/lib/supabase/client";
 
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
 
export type JobStatus = "queued" | "running" | "done" | "empty" | "error";
 
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
 
// Downloads happen through an authenticated fetch + blob rather than a plain
// <a href>, since a raw link can't carry an Authorization header and every
// API route requires one.
async function downloadFile(path: string, fallbackName: string): Promise<void> {
    const res = await apiFetch(path);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match?.[1] || fallbackName;
 
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}
 
export const api = {
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
 
    // Fetched as text and rendered via <iframe srcDoc=...> in the caller.
    getMapHtml: (id: string) => apiFetch(`/api/searches/${id}/map`).then((r) => r.text()),
 
    downloadExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/searches/${id}/excel`, `${cityLabel}.xlsx`),
 
    listHistory: () => apiJson<HistoryRun[]>("/api/history"),
 
    getHistoryRun: (id: string) => apiJson<HistoryDetail>(`/api/history/${id}`),
 
    downloadHistoryExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/history/${id}/excel`, `${cityLabel}.xlsx`),
};