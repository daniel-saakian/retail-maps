"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/app/login/actions";
import StoneMark from "./StoneMark";
import { useJobs } from "@/lib/JobsContext";

const TABS = [
    { href: "/", label: "Search" },
    { href: "/history", label: "History" },
    { href: "/settings", label: "Settings" },
];

export default function NavBar() {
    const pathname = usePathname();



    const { jobs, me } = useJobs();

    if (pathname.startsWith("/login") || pathname.startsWith("/onboarding")) return null;

    const runningCount = jobs.filter((j) => j.status === "queued" || j.status === "running").length;

    return (
        <nav className="border-b border-ink-2/40 bg-ink">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2.5">
                        <StoneMark size={28} />
                        <span className="font-display text-base font-semibold tracking-wide text-paper">
                            Plaza Finder
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        {TABS.map((t) => (
                            <Link
                                key={t.href}
                                href={t.href}
                                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                                    pathname === t.href
                                        ? "bg-ink text-white"
                                        : "text-slate-500 hover:bg-slate-50"
                                }`}
                            >
                                {t.label}
                            </Link>
                        ))}
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    {runningCount > 0 && (
                        <Link
                            href="/"
                            className="flex items-center gap-1.5 text-xs font-semibold text-sky"
                        >
                            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky" />
                            {runningCount} running
                        </Link>
                    )}
                    {me?.first_name && (
                        <span className="flex items-center gap-2 text-xs font-medium text-paper/80">
                            Signed in as {me.first_name}
                            {me.avatar_url ? (
                                <img
                                    src={me.avatar_url}
                                    alt=""
                                    className="h-6 w-6 rounded-full border border-white/20 object-cover"
                                />
                            ) : (
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky text-[10px] font-bold text-white">
                                    {me.first_name[0]?.toUpperCase()}
                                </span>
                            )}
                        </span>
                    )}
                    <button
                        onClick={() => logout()}
                        className="text-xs font-semibold uppercase tracking-[0.1em] text-paper/50 hover:text-paper"
                    >
                        Sign Out
                    </button>
                </div> 
            </div>
        </nav>
    );
}
