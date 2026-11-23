"use client";

import { useEffect, useSyncExternalStore } from "react";
import { api, ProjectionBrand, ProjectionField, ProjectionInputs, ProjectionMarkBody } from "./api";

const norm = (s?: string | null) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

export function addrKey(address?: string | null, city?: string | null, state?: string | null): string {
    return [norm(address), norm(city), norm(state)].join("|");
}

export function keyFromFullAddress(full: string): string {
    const parts = full.split(",").map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 3) return addrKey(parts[0], parts[1], parts[2].split(/\s+/)[0]);
    return addrKey(full, "", "");
}

export function fullAddress(address?: string | null, city?: string | null, state?: string | null): string {
    return [address, city, state].filter((x) => x && x !== "-").join(", ");
}

interface Snapshot {
    loaded: boolean;
    brands: ProjectionBrand[];
    marks: Record<string, string[]>;
}

let snap: Snapshot = { loaded: false, brands: [], marks: {} };
let started = false;
const listeners = new Set<() => void>();

function emit(next: Partial<Snapshot>) {
    snap = { ...snap, ...next };
    listeners.forEach((l) => l());
}

async function load() {
    try {
        const { brands } = await api.projectionAccess();
        if (brands.length === 0) {
            emit({ loaded: true, brands: [], marks: {} });
            return;
        }
        const { marks } = await api.projectionMarks();
        emit({ loaded: true, brands, marks });
    } catch {
        emit({ loaded: true, brands: [], marks: {} });
    }
}

export function refreshProjections() {
    return load();
}

export function useProjections(enabled = true) {
    const s = useSyncExternalStore(
        (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
        () => snap,
        () => snap,
    );
    useEffect(() => {
        if (enabled && !started) { started = true; void load(); }
    }, [enabled]);
    return { ...s, hasAccess: s.brands.length > 0 };
}

export function errorMessage(e: unknown): string {
    const raw = e instanceof Error ? e.message : String(e);
    try {
        const j = JSON.parse(raw);
        if (typeof j.detail === "string") return j.detail;
    } catch { /* not JSON */ }
    return raw;
}

export async function setMark(body: ProjectionMarkBody) {
    const res = await api.putProjectionMark(body);
    const marks = { ...snap.marks };
    if (res.brands.length) marks[body.key] = res.brands;
    else delete marks[body.key];
    emit({ marks });
    return res;
}

export type { ProjectionInputs };

export function defaultInputs(fields: ProjectionField[]): ProjectionInputs {
    return Object.fromEntries(fields.map((f) => [f.id, f.default]));
}