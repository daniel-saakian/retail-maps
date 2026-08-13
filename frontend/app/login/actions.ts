"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export async function login(formData: FormData) {
    const supabase = await createClient();
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    const next = String(formData.get("next") || "/");

    if (!email || !password) {
        redirect(`/login?error=${encodeURIComponent("Email and password are required")}$next=${encodeURIComponent(next)}`);
    }

    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
        redirect(`/login?error=${encodeURIComponent("Invalid email and/or password")}&next=${encodeURIComponent(next)}`);
    }

    revalidatePath("/", "layout");
    const separator = next.includes("?") ? "&" : "?";
    redirect(`${next}${separator}welcome=1`);
}

export async function logout() {
    const supabase = await createClient();
    await supabase.auth.signOut();
    revalidatePath("/","layout");
    redirect("/login?goodbye=1");
}