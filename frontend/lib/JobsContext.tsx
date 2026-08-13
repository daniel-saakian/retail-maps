"use client";
 
import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { HistoryRun, JobDetail, UserProfile, api } from "@/lib/api";
 
interface JobsContextValue {
    jobs: JobDetail[];
    defaultSearchKm: number;
    createSearch: (city: string, searchKm: number, rescrapeDays: number | null) => Promise<void>;
    dismissSearch: (id: string) => Promise<void>;
 
    historyRuns: HistoryRun[];
    historyLoaded: boolean;
    historyLoading: boolean;
    historyError: string | null;
    refreshHistory: () => Promise<void>;
 
    me: UserProfile | null;
    refreshMe: () => Promise<void>;
}
 
const JobsContext = createContext<JobsContextValue | null>(null);
 
export function JobsProvider({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const skip = pathname.startsWith("/login") || pathname.startsWith("/onboarding");
 
    const [jobs, setJobs] = useState<JobDetail[]>([]);
    const [defaultSearchKm, setDefaultSearchKm] = useState(20);
    const jobsRef = useRef<JobDetail[]>([]);
    jobsRef.current = jobs;
 
    const [historyRuns, setHistoryRuns] = useState<HistoryRun[]>([]);
    const [historyLoaded, setHistoryLoaded] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [historyError, setHistoryError] = useState<string | null>(null);
 
    const [me, setMe] = useState<UserProfile | null>(null);
 
    const refreshMe = useCallback(async () => {
        try {
            setMe(await api.getMe());
        } catch {
        }
    }, []);

    useEffect(() => {
        if (skip || !me) return;
        if (!me.first_name || !me.last_name) {
            router.replace("/onboarding");
        }
    }, [me, skip, router]);
 
    const refreshAll = useCallback(async () => {
        const summaries = await api.listSearches();
        const details = await Promise.all(summaries.map((s) => api.getSearch(s.id)));
        setJobs(details);
    }, []);
 
    const refreshActive = useCallback(async () => {
        const current = jobsRef.current;
        const updated = await Promise.all(
            current.map((j) =>
                j.status === "queued" || j.status === "running" ? api.getSearch(j.id) : Promise.resolve(j)
            )
        );
        setJobs(updated);
    }, []);
 
    const refreshHistory = useCallback(async () => {
        setHistoryLoading(true);
        try {
            const runs = await api.listHistory();
            setHistoryRuns(runs);
            setHistoryLoaded(true);
            setHistoryError(null);
        } catch (e) {
            setHistoryError((e as Error).message);
        } finally {
            setHistoryLoading(false);
        }
    }, []);

    useEffect(() => {
        if (skip) return;
        api.defaults().then((d) => setDefaultSearchKm(d.search_km)).catch(() => {});
        refreshAll();
        refreshHistory();
        refreshMe();
    }, [skip]);
 
    useEffect(() => {
        if (skip) return;
        const interval = setInterval(() => {
            const anyActive = jobsRef.current.some(
                (j) => j.status === "queued" || j.status === "running"
            );
            if (anyActive) refreshActive();
        }, 2000);
        return () => clearInterval(interval);
    }, [skip]);
 
    const prevStatuses = useRef<Record<string, string>>({});
    useEffect(() => {
        let finished = false;
        for (const j of jobs) {
            const prev = prevStatuses.current[j.id];
            if (prev && (prev === "queued" || prev === "running") && j.status !== prev) {
                finished = true;
            }
            prevStatuses.current[j.id] = j.status;
        }
        if (finished) refreshHistory();
    }, [jobs, refreshHistory]);
 
    async function createSearch(city: string, searchKm: number, rescrapeDays: number | null) {
        const summary = await api.createSearch(city, searchKm, rescrapeDays);
        const detail = await api.getSearch(summary.id);
        setJobs((prev) => [detail, ...prev]);
    }
 
    async function dismissSearch(id: string) {
        await api.deleteSearch(id);
        setJobs((prev) => prev.filter((j) => j.id !== id));
    }
 
    return (
        <JobsContext.Provider
            value={{
                jobs,
                defaultSearchKm,
                createSearch,
                dismissSearch,
                historyRuns,
                historyLoaded,
                historyLoading,
                historyError,
                refreshHistory,
                me,
                refreshMe,
            }}
        >
            {children}
        </JobsContext.Provider>
    );
}
 
export function useJobs() {
    const ctx = useContext(JobsContext);
    if (!ctx) throw new Error("useJobs must be used within JobsProvider");
    return ctx;
}