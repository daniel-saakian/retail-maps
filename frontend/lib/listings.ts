export function timeAgo(iso?: string | null): string {
    if (!iso) return "";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "";
    const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 48) return `${hrs}h ago`;
    return `${Math.round(hrs / 24)}d ago`;
}

export function formatSf(min?: number | null, max?: number | null): string {
    const lo = min ?? max;
    const hi = max ?? min;
    if (lo == null || hi == null) return "";
    if (lo === hi) return `${lo.toLocaleString()} SF`;
    return `${lo.toLocaleString()}-${hi.toLocaleString()} SF`;
}

const rate_units: Record<string, string> = {
    sf_yr: "$/SF/YR",
    sf_mo: "$/SF/MO",
    month: "/MO",
    year: "/YR",
};

function money(n: number): string {
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function formatRate(
    min?: number | null,
    max?: number | null,
    unit?: string | null
): string {
    if (unit === "negotiable") return "Rate negotiable";
    const lo = min ?? max;
    const hi = max ?? min;
    if (lo == null || hi == null) return "";
    const suffix = (unit && rate_units[unit]) || "";
    return lo === hi ? `${money(lo)}${suffix}` : `${money(lo)}-${money(hi)}${suffix}`;
}

export function mapsLink(p: {
    lat?: number | null;
    lng?: number | null;
    name?: string | null;
    address?: string | null;
    city?: string | null;
    state?: string | null;
}): string {
    const q =
        p.lat != null && p.lng != null
            ? `${p.lat},${p.lng}`
            : [p.name, p.address, p.city, p.state].filter((x) => x && x !== "-").join(", ");
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
}

export function titleCase(s: string): string {
    return s.replace(/\b\w/g, (c) => c.toUpperCase());
}