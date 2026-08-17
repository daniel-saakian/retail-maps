"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export default function OnboardingPage() {
    const router = useRouter();
    const [checking, setChecking] = useState(true);
    const [email,setEmail] = useState("");

    const [firstName,setFirstName] = useState("");
    const [lastName,setLastName] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [avatarFile, setAvatarFile] = useState<File | null>(null);
    const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        api.getMe()
           .then((me) => {
                if (me.first_name && me.last_name) {
                    router.replace("/");
                    return;
                }
                setEmail(me.email);
                setChecking(false);
           })
           .catch(() => {
            router.replace("/login");
           });
    }, []);

    function handleAvatarChange(e:React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file) return;
        setAvatarFile(file);
        setAvatarPreview(URL.createObjectURL(file));
    }

    async function handleSubmit(e:React.FormEvent) {
        e.preventDefault();
        setError(null);

        if (!firstName.trim() || !lastName.trim()) {
            setError("First and last name are required");
            return;
        }
        if (password.length < 8) {
            setError("Password must be at least 8 characters long");
            return;
        }
        if (password !== confirmPassword) {
            setError("Passwords don't match");
            return;
        }

        setSubmitting(true);
        try {
            const supabase = createClient();
            const { error: pwError } = await supabase.auth.updateUser({ password });
            if (pwError) throw new Error(pwError.message);

            await api.updateMe({ first_name: firstName.trim(), last_name: lastName.trim() });

            if (avatarFile) {
                await api.uploadAvatar(avatarFile);
            }

            router.push("/");
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setSubmitting(false);
        }
    }

    if (checking) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-paper">
                <p className="text-sm text-charcoal">Loading...</p>
            </main>
        );
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-paper px-6 py-10">
            <div className="w-full max-w-md">
                <div className="mb-8 flex flex-col items-col gap-3 text-center">
                    <Image src="/logo.png" alt="Stone Commercial" height={140} width={40} />
                    <div>
                        <h1 className="font-display text-2xl font-bold text-ink">Welcome to Plaza Finder ----CHANGE THIS----</h1>
                        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-charcoal">
                            {email}
                        </p>
                    </div>
                </div>

                <div className="rounded-xl border border-line bg-white p-8 shadow-sm">
                    <div className="wedge-divider mb-6">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-charcoal">
                            Set up your account
                        </span>
                    </div>

                    {error && (
                        <div className="mb-5 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger-dark">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                        <div className="flex items-center gap-4">
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full border border-line bg-paper-dim"
                            >
                                {avatarPreview ? (
                                    <img src={avatarPreview} alt="Avatar Preview" className="h-full w-full object-cover" />
                                ) : (
                                    <span className="flex h-full w-full items-center justify-center text-xs text-charcoal/60">
                                        Add photo
                                    </span>
                                )}
                            </button>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="img/png,image/jpeg,image/webp,image/gif"
                                onChange={handleAvatarChange}
                                className="hidden"
                            />
                            <p className="text-xs text-charcoal/70">
                                Optional. Click the circle to choose a profile picture.
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <label className="text-sm">
                                <span className="mb-1 block font-medium text-charcoal">First Name</span>
                                <input
                                    value={firstName}
                                    onChange={(e) => setFirstName(e.target.value)}
                                    required
                                    className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                />
                            </label>
                            <label className="text-sm">
                                <span className="mb-1 block font-medium text-charcoal">Last Name</span>
                                <input
                                    value={lastName}
                                    onChange={(e) => setLastName(e.target.value)}
                                    required
                                    className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                />
                            </label>
                        </div>
                        
                        <label className="text-sm">
                            <span className="mb-1 block font-medium text-charcoal">Password</span>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                minLength={8}
                                autoComplete="new-password"
                                className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                            />
                        </label>
                        <label className="text-sm">
                            <span className="mb-1 block font-medium text-charcoal">Confirm Password</span>
                            <input
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                required
                                minLength={8}
                                autoComplete="new-password"
                                className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                            />
                        </label>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="mt-2 rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-50"
                        >
                            {submitting ? "Setting up...": "Finish setup"}
                        </button>
                    </form>
                </div>
            </div>
        </main>
    );
}