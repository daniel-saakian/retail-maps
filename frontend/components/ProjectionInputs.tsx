"use client";

import type { ProjectionField, ProjectionInputs } from "@/lib/api";


export default function ProjectionInputFields({
    fields, value, onChange, label, size="xs",
}: {
    fields: ProjectionField[];
    value: ProjectionInputs;
    onChange: (next: ProjectionInputs) => void;
    label: string;
    size?: "xs" | "sm";
}) {
    const text = size === "sm"  ? "text-sm" : "text-xs";
    return (
        <>
            {fields.map((f) => 
                f.type === "select" ? (
                    <select
                        key={f.id}
                        value={String(value[f.id] ?? f.default)}
                        onChange={(e) => onChange({...value, [f.id]: e.target.value})}
                        aria-label={`${label} ${f.label}`}
                        className={`rounded border border-line bg-white px-2 py-1 ${text} text-ink`}
                    >
                        {(f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                ): (
                    <label key={f.id} className="flex items-center gap-1.5">
                        <input
                            type="checkbox"
                            checked={Boolean(value[f.id] ?? f.default)}
                            onChange={(e) => onChange({ ...value, [f.id]: e.target.checked })}
                            className={`rounded border border-line bg-white px-2 py-1 ${text} text-ink`}
                        />
                        {f.label}
                    </label>
                ),
            )}
        </>
    );
}