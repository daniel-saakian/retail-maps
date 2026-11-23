"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ProjectionInputFields from "@/components/ProjectionInputs"
import {
    addrKey, defaultInputs, errorMessage, fullAddress, ProjectionInputs, setMark, useProjections,
} from "@/lib/projections";

interface Props {
    name?: string | null;
    address?: string | null;
    city?: string | null;
    state?: string | null;
}







export default function SaveProjectionControl({ name, address, city, state }: Props) {
    const { loaded, brands, marks, hasAccess } = useProjections();
    const [open, setOpen] = useState(false);
    const [picked, setPicked] = useState<string[]>([]);
    const [inputs, setInputs] = useState<Record<string, ProjectionInputs>>({});
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const wrap = useRef<HTMLDivElement>(null);

    const hasStreet = !!address && address !== "-";
    const key = addrKey(address, city, state);
    const saved = marks[key] || [];

    useEffect(() => {
        if (!open) return;
        const onDown = (e: MouseEvent) => {
            if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    if (!loaded || !hasAccess || !hasStreet) return null;

    const openPopup = () => {
        setPicked(saved);
        setInputs(Object.fromEntries(brands.map((b) => [b.id, defaultInputs(b.fields)])));
        setError(null);
        setOpen(true);
    };

    const toggle = (id: string) =>
        setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

    const unchanged = picked.length === saved.length && picked.every((b) => saved.includes(b));
    const removing = picked.length === 0 && saved.length > 0;

    const submit = async () => {
        setBusy(true);
        setError(null);
        try {
            await setMark({
                key,
                address: fullAddress(address, city, state),
                name, city, state,
                source: "digest",
                brands: picked,
                inputs,
            });
            setOpen(false);
        } catch (e) {
            setError(errorMessage(e));
        } finally {
            setBusy(false);
        }
    };

    const checked = saved.length > 0;
    const labels = saved.map((id) => brands.find((b) => b.id === id)?.label || id).join(", ");

    return (
        <div ref={wrap} className="relative">
            <button
                type="button"
                role="checkbox"
                aria-checked={checked}
                aria-haspopup="dialog"
                aria-expanded={open}
                onClick={() => (open ? setOpen(false) : openPopup())}
                className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-xs font-semibold transition ${
                    checked
                        ? "border-sky bg-sky/10 text-ink"
                        : "border-line bg-white text-charcoal hover:border-ink/40"
                }`}
            >
                <span
                    className={`flex h-4 w-4 items-center justify-center rounded border ${
                        checked ? "border-sky bg-sky text-white" : "border-charcoal/40 bg-white"
                    }`}
                    aria-hidden
                >
                    {checked && (
                        <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M2.5 6.5l2.2 2.2L9.5 3.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    )}
                </span>
                {checked ? `Projection · ${labels}` : "Projection"}
            </button>

            {open && (
                <div
                    role="dialog"
                    aria-label="Save projection"
                    className="absolute right-0 top-full z-30 mt-2 w-72 rounded-lg border border-line bg-white p-4 shadow-lg"
                >
                    <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">
                        Save projection under
                    </div>
                    <p className="mt-1 truncate text-sm font-medium text-ink">{name || address}</p>

                    <ul className="mt-3 space-y-2">
                        {brands.map((b) => {
                            const on = picked.includes(b.id);
                            const already = saved.includes(b.id);
                            return (
                                <li key={b.id} className="rounded-lg border border-line p-2.5">
                                    <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-ink">
                                        <input
                                            type="checkbox"
                                            checked={on}
                                            onChange={() => toggle(b.id)}
                                            className="h4 w-4 accent-[#2AA7DE]"
                                        />
                                        {b.label}
                                        {already && <span className="text-xs font-normal text-charcoal/70">saved</span>}
                                    </label>
                                    {on && !already && (
                                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 pl-6 text-xs text-charcoal">
                                            <ProjectionInputFields
                                                fields={b.fields}
                                                label={b.label}
                                                value={inputs[b.id] ?? defaultInputs(b.fields)}
                                                onChange={(next) => setInputs((m) => ({ ...m, [b.id]: next }))}
                                            />
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>

                    {error && <p className="mt-3 text-xs text-danger">{error}</p>}

                    <div className="mt-4 flex items-center justify-between gap-2">
                        {saved.length > 0 ? (
                            <Link href="/projections" className="text-xs font-semibold text-sky hover:underline">
                                View Projections →
                            </Link>
                        ) : <span />}
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setOpen(false)}
                                className="rounded-lg px-3 py-1.5 text-xs font-semibold text-charcoal hover:bg-ink/5"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={submit}
                                disabled={busy || unchanged}
                                className={`rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition disabled:opacity-40 ${
                                    removing ? "bg-danger" : "bg-ink hover:bg-ink/90"
                                }`}
                            >
                                {busy ? "Saving..." : removing ? "Remove" : "Save"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}