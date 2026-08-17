import { login } from "./actions";
import Image from "next/image";

export default async function LoginPage({
    searchParams,
}: {
    searchParams: Promise<{ error?: string; next?: string }>;
}) {
    const params = await searchParams;

    return (
        <main className="flex min-h-screen items-center justify-center bg-paper px-6">
            <div className="w-full max-w-sm">
                <div className="mb-8 flex flex-col items-center gap-3 text-center">
                    <Image src="/logo.png" alt="Stone Commercial" height={1200} width={300} />
                    <div>
                        <h1 className="font-display text-2xl font-bold text-ink">Plaza Finder</h1>
                        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-charcoal">
                            Stone Commercial
                        </p>
                    </div>
                </div>

                <div className="rounded-xl border border-line bg-white p-8 shadow-sm">
                    <div className="wedge-divider mb-6">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-charcoal">
                            Sign in
                        </span>
                    </div>

                    {params.error && (
                        <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                            {params.error}
                        </div>
                    )}
                    <form action={login} className="flex flex-col gap-4">
                        <input type="hidden" name="next" value={params.next || "/"} />
                        <label className="text-sm">
                            <span className="mb-1 block font-medium text-charcoal">Email</span>
                            <input
                                type="email"
                                name="email"
                                required
                                autoComplete="email"
                                className="w-full rounded-lg bordeer border-line bg-paper px-3 py-3 text-sm text-ink outline-none transition focus:border-sky focus:ring-1 focus:rink-sky"
                            />
                        </label>
                        <label className="text-sm">
                            <span className="mb-1 block font-medium text-charcoal">Password</span>
                            <input
                                type="password"
                                name="password"
                                required
                                autoComplete="current-password"
                                className="w-full rounded-lg bordeer border-line bg-paper px-3 py-3 text-sm text-ink outline-none transition focus:border-sky focus:ring-1 focus:rink-sky"
                            />
                        </label>
                        <button
                            type="submit"
                            className="mt-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2"
                        >
                            Sign in
                        </button>
                    </form>
                </div>

                <p className="mt-6 text-center text-xs text-charcoal/70">
                    Accounts are invite-only. Contact daniel@stonecommercial.com
                </p>
            </div>
        </main>
    );
}