


import { createClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type FieldSource = "auto" | "listing" | "ai" | "manual";

export interface ReviewField {
    id: string;
    section: string;
    label: string;
    kind: "text" | "long";
    source: FieldSource;
    hint?: string | null;
}

export interface ReviewTableSpec {
    id: string;
    section: string;
    label: string;
    columns: [string, string, number][];
    source: FieldSource;
    max_rows: number;
    fixed_rows?: boolean;
    row_labels?: string[];
    hint?: string | null;
}

export interface ReviewSchema {
    sections: { id: string; label: string }[];
    fields: ReviewField[];
    tables: ReviewTableSpec[];
    swot: { section: string; max_items: number; quadrants: SwotKey[] };
}

export type SwotKey = "strengths" | "weaknesses" | "opportunities" | "threats";
export type Swot = Record<SwotKey, string[]>;
export type TableRow = Record<string, string>;

export interface PrefillValue {
    value: string;
    source: FieldSource;
    note?: string | null;
}

export interface ListingCandidate {
    id: string;
    kind?: string | null;
    summary: string;
    distance_mi?: number | null;
    center_name?: string | null;
    listing_url?: string | null;
    flyer_url?: string | null;
    photo_url?: string | null;
    facts: Record<string, unknown>;
    fields: Record<string, PrefillValue>;
}

export interface PrefillResponse {
    fields: Record<string, PrefillValue>;
    tables: Record<string, TableRow[]>;
    listings: ListingCandidate[];
    context: Record<string, unknown>;
    warnings: string[];
}

export interface FormState {
    fields: Record<string, string>;
    tables: Record<string, TableRow[]>;
    swot: Swot;
}

async function authHeaders(): Promise<HeadersInit> {
    const supabase = createClient();
    const {
        data: {session},
    } = await supabase.auth.getSession();
    if (!session) throw new Error("Not signed in");
    return { Authorization: `Bearer ${session.access_token}`};
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = {
        ...(await authHeaders()),
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(init.headers || {}),
    };
    const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
    if (res.status === 401) {
        window.location.href = "/login";
        throw new Error("Session expired");
    }
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        let msg = text;
        try {
            msg = JSON.parse(text).detail || text;
        } catch {
            /* plain text */
        }
        throw new Error(msg || `Request failed (${res.status})`);
    }
    return res
}

export const hbReview = {
    schema: async (): Promise<ReviewSchema> => (await call("/api/hb-review/schema")).json(),

    prefill: async (
        address: string,
        coords?: { lat: number; lon: number},
        signal?: AbortSignal
    ): Promise<PrefillResponse> => 
        (
            await call("/api/hb-review/prefill", {
                method: "POST",
                body: JSON.stringify({ address, lat: coords?.lat ?? null, lon: coords?.lon ?? null }),
                signal,
            })
        ).json(),

    render: async (state: FormState, filename?: string): Promise<{blob: Blob; filename: string}> => {
        const res = await call("/api/hb-review/render", {
            method: "POST",
            body: JSON.stringify({ ...state, filename }),
        });
        const blob = await res.blob();
        const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
        return { blob, filename: match?.[1] || "HB_Site_Review.docx" };
    },
};

export function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const emptySwot = (): Swot => ({ strengths: [], weaknesses: [], opportunities: [], threats: [] });