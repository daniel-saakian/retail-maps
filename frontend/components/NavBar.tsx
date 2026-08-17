"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/app/login/actions";
import StoneMark from "./StoneMark";
import { useJobs } from "@/lib/JobsContext";

const TABS = [
    { href: "/", label: "Search" },
    { href: "/history", label: "History" },
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
                    <ProfileMenu />
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

function initials (firstName?: string | null, lastName?: string | null): string {
    const a = firstName?.[0] || "";
    const b = lastName?.[0] || "";
    return (a + b).toUpperCase() || "?";
}

function ProfileMenu() {
    const { me } = useJobs();
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    
    useEffect(() => {
        if (!open) return;
        function handleClick(e:MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, [open]);

    if (!me) return null

    return (
        <div ref={containerRef} className="group relative">
            <button
                onClick={() => setOpen((o) => !o)}
                className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full border border-white/20 bg-sky text-[11px] font-bold text-white transition hover:border-white/40"
                aria-label="Account menu"
            >
                {me.avatar_url ? (
                    <img src={me.avatar_url} alt="" className="h-full w-full object-cover" />
                ) : (
                    initials(me.first_name, me.last_name)
                )}
            </button>
 
            <div
                className={`absolute right-0 top-full z-50 mt-2 w-52 origin-top-right rounded-lg border border-line bg-white shadow-lg transition-all duration-150 ease-out ${
                    open
                        ? "visible translate-y-0 opacity-100"
                        : "invisible -translate-y-1 opacity-0"
                } group-hover:visible group-hover:translate-y-0 group-hover:opacity-100`}
            >
                {me.first_name && (
                    <div className="border-b border-line px-4 py-2.5 text-xs font-semibold text-charcoal">
                        Signed in as {me.first_name}
                    </div>
                )}
                <Link
                    href="/profile"
                    onClick={() => setOpen(false)}
                    className="block px-4 py-2.5 text-sm text-ink hover:bg-paper-dim"
                >
                    Profile
                </Link>
                {me.role === "staff" && (
                    <Link
                        href="/settings"
                        onClick={() => setOpen(false)}
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-ink hover:bg-paper-dim"
                    >
                        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 text-charcoal">
                            <path
                                fillRule="evenodd"
                                d="M8.34 1.804A1 1 0 0 1 9.32 1h1.36a1 1 0 0 1 .98.804l.295 1.473c.497.144.971.342 1.416.587l1.25-.834a1 1 0 0 1 1.262.125l.962.962a1 1 0 0 1 .125 1.262l-.834 1.25c.245.445.443.919.587 1.416l1.473.295a1 1 0 0 1 .804.98v1.36a1 1 0 0 1-.804.98l-1.473.295a5.973 5.973 0 0 1-.587 1.416l.834 1.25a1 1 0 0 1-.125 1.262l-.962.962a1 1 0 0 1-1.262.125l-1.25-.834c-.445.245-.919.443-1.416.587l-.295 1.473a1 1 0 0 1-.98.804H9.32a1 1 0 0 1-.98-.804l-.295-1.473a5.97 5.97 0 0 1-1.416-.587l-1.25.834a1 1 0 0 1-1.262-.125l-.962-.962a1 1 0 0 1-.125-1.262l.834-1.25a5.97 5.97 0 0 1-.587-1.416l-1.473-.295a1 1 0 0 1-.804-.98V9.32a1 1 0 0 1 .804-.98l1.473-.295c.144-.497.342-.971.587-1.416l-.834-1.25a1 1 0 0 1 .125-1.262l.962-.962a1 1 0 0 1 1.262-.125l1.25.834c.445-.245.919-.443 1.416-.587l.295-1.473ZM10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
                                clipRule="evenodd"
                            />
                        </svg>
                        Settings
                    </Link>
                )}
            </div>
        </div>
    );
}
