"use client";
import SearchForm from "@/components/SearchForm";
import JobCard from "@/components/JobCard";
import { useJobs } from "@/lib/JobsContext";

export default function Home() {
    const { jobs, defaultSearchKm, createSearch, dismissSearch } = useJobs();

    return(
        <main className="mx-auto max-w-6xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Plaza Finder</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-ws">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Retail Site Search
                    </span>
                </div>
                <p className="text-sm text-charcoal">
                    Search a city, watch it run, and get the exportable map
                </p>
            </header>

            <SearchForm defaultSearchKm={defaultSearchKm} onSubmit={createSearch} />
            
            <div className="mt-8 flex flex-col gap-5">
                {jobs.length === 0 && (
                    <p className="rounded-lg border border-dashed border-line bg-paper-dim/50 p-6 text-center text-sm text-charcoal/70">
                        No Searches Yet
                    </p>
                )}
                {jobs.map((job) => (
                    <JobCard key={job.id} job={job} onDismiss={dismissSearch} />
                ))}
            </div>
        </main>
    );
}