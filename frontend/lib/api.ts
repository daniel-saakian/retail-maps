import { createClient } from "@/lib/supabase/client";
import { User } from "@supabase/supabase-js";
 
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
 
export interface UserProfile {
    id: string;
    email: string;
    role: string;
    created_at: string;
    first_name?: string | null;
    last_name?: string | null;
    avatar_url?: string | null;
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
 
    getMapHtml: (id: string) => apiFetch(`/api/searches/${id}/map`).then((r) => r.text()),
 
    downloadExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/searches/${id}/excel`, `${cityLabel}.xlsx`),
 
    listHistory: () => apiJson<HistoryRun[]>("/api/history"),
 
    getHistoryRun: (id: string) => apiJson<HistoryDetail>(`/api/history/${id}`),
 
    downloadHistoryExcel: (id: string, cityLabel: string) =>
        downloadFile(`/api/history/${id}/excel`, `${cityLabel}.xlsx`),
 
    getMe: () => apiJson<UserProfile>("/api/me"),

    updateMe: (fields: { first_name?: string; last_name?: string}) =>
        apiJson<UserProfile>("/api/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(fields),
        }),
    
    uploadAvatar: (file:File) => {
        const formData = new FormData();
        formData.append("file", file);
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
};