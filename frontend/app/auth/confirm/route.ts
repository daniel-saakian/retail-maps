import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
 
export async function GET(request: NextRequest) {
    const { searchParams, origin } = request.nextUrl;
    const token_hash = searchParams.get("token_hash");
    const type = searchParams.get("type") as EmailOtpType | null;
    
    const redirectParam = searchParams.get("redirect_to") || "/";
    const destination = redirectParam.startsWith("http") ? redirectParam : `${origin}${redirectParam}`
    if (token_hash && type) {
        const supabase = await createClient();
        const { error } = await supabase.auth.verifyOtp({ type, token_hash });
        if (!error) {
            return NextResponse.redirect(destination);
        }
    }
 
    return NextResponse.redirect(`${origin}/login?error=${encodeURIComponent("That invite link is invalid or has expired.")}`);
}