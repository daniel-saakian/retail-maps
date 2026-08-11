const KM_PER_MILE = 1.60934

export function kmToMiles(km:number): number {
    return Math.round((km/KM_PER_MILE) * 10) / 10;
}

export function splitCommaList(s: string | null | undefined): string[] {
    if (!s || s === "-") return [];
    return s.split(",").map((x) => x.trim()).filter(Boolean);
}

export function splitBrokerList(s:string | null | undefined): string[] {
    if (!s || s === "-") return [];
    const seen = new Set<string>();
    const out: string[] = [];
    for (const raw of s.split(";")) {
        const item = raw.trim();
        if (!item || item === "-" || seen.has(item)) continue;
        seen.add(item);
        out.push(item);
    }
    return out;
}