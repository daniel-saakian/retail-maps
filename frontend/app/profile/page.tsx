"use client";
 
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { useJobs } from "@/lib/JobsContext";
 
export default function ProfilePage() {
    const { me, refreshMe } = useJobs();
 
    if (!me) {
        return (
            <main className="mx-auto max-w-2xl px-6 py-10">
                <p className="text-sm text-charcoal">Loading...</p>
            </main>
        );
    }
 
    return (
        <main className="mx-auto max-w-2xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Profile</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Your Account
                    </span>
                </div>
            </header>
 
            <ProfileForm me={me} onUpdated={refreshMe} />
        </main>
    );
}
 
function ProfileForm({
    me,
    onUpdated,
}: {
    me: NonNullable<ReturnType<typeof useJobs>["me"]>;
    onUpdated: () => Promise<void>;
}) {
    const router = useRouter();
    const fileInputRef = useRef<HTMLInputElement>(null);
 
    const [firstName, setFirstName] = useState(me.first_name || "");
    const [lastName, setLastName] = useState(me.last_name || "");
    const [savingProfile, setSavingProfile] = useState(false);
    const [profileError, setProfileError] = useState<string | null>(null);
    const [profileSaved, setProfileSaved] = useState(false);
 
    const [uploadingAvatar, setUploadingAvatar] = useState(false);
    const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
 
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [savingPassword, setSavingPassword] = useState(false);
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [passwordSaved, setPasswordSaved] = useState(false);
 
    const [deleting, setDeleting] = useState(false);
 
    async function handleSaveProfile(e: React.FormEvent) {
        e.preventDefault();
        if (!firstName.trim() || !lastName.trim()) {
            setProfileError("First and last name are required.");
            return;
        }
        setSavingProfile(true);
        setProfileError(null);
        setProfileSaved(false);
        try {
            await api.updateMe({ first_name: firstName.trim(), last_name: lastName.trim() });
            await onUpdated();
            setProfileSaved(true);
            setTimeout(() => setProfileSaved(false), 2000);
        } catch (e) {
            setProfileError((e as Error).message);
        } finally {
            setSavingProfile(false);
        }
    }
 
    async function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file) return;
        setAvatarPreview(URL.createObjectURL(file));
        setUploadingAvatar(true);
        try {
            await api.uploadAvatar(file);
            await onUpdated();
        } catch (e) {
            alert((e as Error).message);
        } finally {
            setUploadingAvatar(false);
        }
    }
 
    async function handleChangePassword(e: React.FormEvent) {
        e.preventDefault();
        setPasswordError(null);
        setPasswordSaved(false);
        if (newPassword.length < 8) {
            setPasswordError("Password must be at least 8 characters.");
            return;
        }
        if (newPassword !== confirmPassword) {
            setPasswordError("Passwords don't match.");
            return;
        }
        setSavingPassword(true);
        try {
            const supabase = createClient();
            const { error } = await supabase.auth.updateUser({ password: newPassword });
            if (error) throw new Error(error.message);
            setNewPassword("");
            setConfirmPassword("");
            setPasswordSaved(true);
            setTimeout(() => setPasswordSaved(false), 2000);
        } catch (e) {
            setPasswordError((e as Error).message);
        } finally {
            setSavingPassword(false);
        }
    }
 
    async function handleDeleteSelf() {
        const confirmed = window.confirm(
            "Delete your own account permanently? This cannot be undone -- you'll be signed out immediately."
        );
        if (!confirmed) return;
 
        setDeleting(true);
        try {
            await api.deleteOwnAccount();
            const supabase = createClient();
            await supabase.auth.signOut();
            router.push("/login");
        } catch (e) {
            alert((e as Error).message);
            setDeleting(false);
        }
    }
 
    const avatarSrc = avatarPreview || me.avatar_url;
    const initials = ((me.first_name?.[0] || "") + (me.last_name?.[0] || "")).toUpperCase() || "?";
 
    return (
        <section className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <div className="flex items-center gap-4">
                <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingAvatar}
                    className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full border border-line bg-sky text-sm font-bold text-white"
                >
                    {avatarSrc ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={avatarSrc} alt="" className="h-full w-full object-cover" />
                    ) : (
                        <span className="flex h-full w-full items-center justify-center">{initials}</span>
                    )}
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    onChange={handleAvatarChange}
                    className="hidden"
                />
                <div className="text-sm text-charcoal">
                    <p className="text-ink">{me.email}</p>
                    <p className="mt-0.5 text-xs uppercase tracking-wide text-charcoal/70">Role: {me.role}</p>
                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploadingAvatar}
                        className="mt-1 text-xs font-semibold text-sky hover:underline disabled:opacity-50"
                    >
                        {uploadingAvatar ? "Uploading..." : "Change photo"}
                    </button>
                </div>
            </div>
 
            <form onSubmit={handleSaveProfile} className="mt-5 border-t border-line pt-4">
                <div className="grid grid-cols-2 gap-3">
                    <label className="text-sm">
                        <span className="mb-1 block font-medium text-charcoal">First name</span>
                        <input
                            value={firstName}
                            onChange={(e) => setFirstName(e.target.value)}
                            className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                        />
                    </label>
                    <label className="text-sm">
                        <span className="mb-1 block font-medium text-charcoal">Last name</span>
                        <input
                            value={lastName}
                            onChange={(e) => setLastName(e.target.value)}
                            className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                        />
                    </label>
                </div>
                {profileError && <p className="mt-2 text-xs text-danger-dark">{profileError}</p>}
                <button
                    type="submit"
                    disabled={savingProfile}
                    className="mt-3 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-ink-2 disabled:opacity-50"
                >
                    {savingProfile ? "Saving..." : profileSaved ? "Saved" : "Save name"}
                </button>
            </form>
 
            <form onSubmit={handleChangePassword} className="mt-5 border-t border-line pt-4">
                <p className="mb-2 text-sm font-medium text-charcoal">Change password</p>
                <div className="grid grid-cols-2 gap-3">
                    <input
                        type="password"
                        placeholder="New password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        autoComplete="new-password"
                        className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    />
                    <input
                        type="password"
                        placeholder="Confirm new password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        autoComplete="new-password"
                        className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    />
                </div>
                {passwordError && <p className="mt-2 text-xs text-danger-dark">{passwordError}</p>}
                <button
                    type="submit"
                    disabled={savingPassword || !newPassword}
                    className="mt-3 rounded-lg border border-line px-4 py-2 text-sm font-semibold text-ink hover:bg-paper-dim disabled:opacity-50"
                >
                    {savingPassword ? "Saving..." : passwordSaved ? "Saved" : "Update password"}
                </button>
            </form>
 
            <div className="mt-5 border-t border-line pt-4">
                <button
                    onClick={handleDeleteSelf}
                    disabled={deleting}
                    className="rounded-lg border border-danger px-4 py-2 text-sm font-semibold text-danger hover:bg-danger/10 disabled:opacity-50"
                >
                    {deleting ? "Deleting..." : "Delete my account"}
                </button>
            </div>
        </section>
    );
}