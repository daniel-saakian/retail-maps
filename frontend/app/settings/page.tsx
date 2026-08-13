"use client";
 
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { UserProfile, api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
 
export default function SettingsPage() {
    const [me, setMe] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
 
    function refreshMe() {
        return api.getMe()
            .then(setMe)
            .catch((e) => setError((e as Error).message));
    }
 
    useEffect(() => {
        refreshMe().finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
 
    return (
        <main className="mx-auto max-w-3xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Settings</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Account &amp; Team
                    </span>
                </div>
            </header>
 
            {loading && <p className="text-sm text-charcoal">Loading...</p>}
            {error && <p className="rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>}
 
            {me && (
                <div className="flex flex-col gap-8">
                    <MyAccountSection me={me} onUpdated={refreshMe} />
                    {me.role === "staff" && <TeamManagementSection me={me} />}
                </div>
            )}
        </main>
    );
}
 
function MyAccountSection({ me, onUpdated }: { me: UserProfile; onUpdated: () => Promise<void> }) {
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
 
    return (
        <section className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <h2 className="font-display text-lg font-bold text-ink">My Account</h2>
 
            <div className="mt-4 flex items-center gap-4 border-t border-line pt-4">
                <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingAvatar}
                    className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full border border-line bg-paper-dim"
                >
                    {avatarSrc ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={avatarSrc} alt="" className="h-full w-full object-cover" />
                    ) : (
                        <span className="flex h-full w-full items-center justify-center text-xs text-charcoal/60">
                            Add photo
                        </span>
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
 
function TeamManagementSection({ me }: { me: UserProfile }) {
    const [users, setUsers] = useState<UserProfile[]>([]);
    const [loadingUsers, setLoadingUsers] = useState(true);
    const [usersError, setUsersError] = useState<string | null>(null);
 
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("member");
    const [inviting, setInviting] = useState(false);
    const [inviteError, setInviteError] = useState<string | null>(null);
 
    function refreshUsers() {
        setLoadingUsers(true);
        api.listUsers()
            .then(setUsers)
            .catch((e) => setUsersError((e as Error).message))
            .finally(() => setLoadingUsers(false));
    }
 
    useEffect(() => {
        refreshUsers();
    }, []);
 
    async function handleInvite(e: React.FormEvent) {
        e.preventDefault();
        if (!inviteEmail.trim()) return;
        setInviting(true);
        setInviteError(null);
        try {
            await api.inviteUser(inviteEmail.trim(), inviteRole);
            setInviteEmail("");
            refreshUsers();
        } catch (e) {
            setInviteError((e as Error).message);
        } finally {
            setInviting(false);
        }
    }
 
    async function handleRoleChange(userId: string, role: string) {
        try {
            await api.updateUserRole(userId, role);
            refreshUsers();
        } catch (e) {
            alert((e as Error).message);
        }
    }
 
    async function handleDeleteUser(userId: string, email: string) {
        const confirmed = window.confirm(`Delete ${email}'s account permanently?`);
        if (!confirmed) return;
        try {
            await api.deleteUser(userId);
            refreshUsers();
        } catch (e) {
            alert((e as Error).message);
        }
    }
 
    return (
        <section className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <h2 className="font-display text-lg font-bold text-ink">Team Management</h2>
            <p className="mt-1 text-xs text-charcoal/70">
                Visible only to staff. Invite new users and manage roles below.
            </p>
 
            <form onSubmit={handleInvite} className="mt-4 flex flex-wrap items-end gap-3 border-t border-line pt-4">
                <label className="flex-1 text-sm">
                    <span className="mb-1 block font-medium text-charcoal">Invite by email</span>
                    <input
                        type="email"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        placeholder="new.person@stonecommercial.com"
                        className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    />
                </label>
                <label className="text-sm">
                    <span className="mb-1 block font-medium text-charcoal">Role</span>
                    <select
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}
                        className="rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky"
                    >
                        <option value="member">Member</option>
                        <option value="staff">Staff</option>
                    </select>
                </label>
                <button
                    type="submit"
                    disabled={inviting || !inviteEmail.trim()}
                    className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-ink-2 disabled:opacity-40"
                >
                    {inviting ? "Inviting..." : "Send invite"}
                </button>
            </form>
            {inviteError && (
                <p className="mt-2 rounded-lg bg-danger/10 p-2 text-xs text-danger-dark">{inviteError}</p>
            )}
 
            <div className="mt-6 border-t border-line pt-4">
                {loadingUsers && <p className="text-sm text-charcoal">Loading users...</p>}
                {usersError && <p className="text-sm text-danger-dark">{usersError}</p>}
                {!loadingUsers && !usersError && (
                    <div className="overflow-hidden rounded-lg border border-line">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-ink text-paper">
                                <tr>
                                    <th className="px-3 py-2 font-semibold">Email</th>
                                    <th className="px-3 py-2 font-semibold">Role</th>
                                    <th className="px-3 py-2 font-semibold">Joined</th>
                                    <th className="px-3 py-2 font-semibold"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((u, i) => {
                                    const isSelf = u.id === me.id;
                                    return (
                                        <tr key={u.id} className={i % 2 ? "bg-paper-dim/60" : "bg-white"}>
                                            <td className="px-3 py-2 align-middle text-ink">{u.email}</td>
                                            <td className="px-3 py-2 align-middle">
                                                <select
                                                    value={u.role}
                                                    disabled={isSelf}
                                                    onChange={(e) => handleRoleChange(u.id, e.target.value)}
                                                    className="rounded border border-line bg-paper px-2 py-1 text-xs disabled:opacity-50"
                                                    title={isSelf ? "You can't change your own role" : undefined}
                                                >
                                                    <option value="member">Member</option>
                                                    <option value="staff">Staff</option>
                                                </select>
                                            </td>
                                            <td className="px-3 py-2 align-middle font-mono text-charcoal">
                                                {new Date(u.created_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-3 py-2 align-middle text-right">
                                                {!isSelf && (
                                                    <button
                                                        onClick={() => handleDeleteUser(u.id, u.email)}
                                                        className="text-xs font-semibold text-danger hover:underline"
                                                    >
                                                        Delete
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </section>
    );
}