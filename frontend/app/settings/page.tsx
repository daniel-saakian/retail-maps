"use client";
 
import { useEffect, useState } from "react";
import { UserProfile, api } from "@/lib/api";
import { useJobs } from "@/lib/JobsContext";
 
export default function SettingsPage() {
    const { me } = useJobs();
 
    if (!me) {
        return (
            <main className="mx-auto max-w-3xl px-6 py-10">
                <p className="text-sm text-charcoal">Loading...</p>
            </main>
        );
    }
 
    if (me.role !== "staff") {
        return (
            <main className="mx-auto max-w-3xl px-6 py-10">
                <p className="rounded-lg border border-dashed border-line bg-paper-dim/50 p-6 text-center text-sm text-charcoal/70">
                    You don't have permission to view this page.
                </p>
            </main>
        );
    }
 
    return (
        <main className="mx-auto max-w-3xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Settings</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Team Management
                    </span>
                </div>
            </header>
 
            <TeamManagementSection me={me} />
        </main>
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
                Invite new users and manage roles below.
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