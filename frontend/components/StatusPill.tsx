import { JobStatus } from "@/lib/api";
 
const STYLE: Record<JobStatus, { bg: string; label: string }> = {
    queued: { bg: "bg-charcoal/50", label: "Queued" },
    running: { bg: "bg-sky", label: "Running" },
    done: { bg: "bg-success", label: "Done" },
    empty: { bg: "bg-brass", label: "No results" },
    error: { bg: "bg-danger", label: "Error" },
};
 
export default function StatusPill({ status }: { status: JobStatus }) {
    const s = STYLE[status];
    return (
        <span
            className={`inline-block rounded-full px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-white ${s.bg}`}
        >
            {s.label}
        </span>
    );
}