import NextAuth, { CredentialsSignin } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { AppUser } from "@/types/next-auth";

class LoginError extends CredentialsSignin {
  constructor(code: string) {
    super();
    this.code = code;
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  trustHost: true,
  providers: [
    Credentials({
      credentials: { email: {}, password: {} },
      async authorize(credentials) {
        const res = await fetch(`${process.env.API_BASE_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials?.email,
            password: credentials?.password,
          }),
        });
        if (res.status === 429) throw new LoginError("rate_limited");
        if (!res.ok) throw new LoginError("invalid_credentials");
        const data = await res.json();
        return {
          id: data.user.id,
          name: data.user.name,
          email: data.user.email,
          role: data.user.role,
          municipalityId: data.user.municipality_id,
          municipalityName: data.user.municipality_name ?? null,
          departmentIds: data.user.department_ids,
          language: data.user.language,
          digestEnabled: data.user.digest_enabled,
          apiToken: data.access_token,
        };
      },
    }),
  ],
  callbacks: {
    jwt({ token, user, trigger, session }) {
      if (user) {
        const { apiToken, ...appUser } = user;
        token.apiToken = apiToken;
        token.user = appUser as AppUser;
      }
      if (trigger === "update" && session) {
        // session here is the arg passed to update() — partial AppUser + optional apiToken
        const patch = session as { user?: Partial<AppUser>; apiToken?: string };
        token.user = { ...token.user, ...(patch.user ?? {}) };
        if (patch.apiToken) token.apiToken = patch.apiToken;
      }
      return token;
    },
    session({ session, token }) {
      session.user = token.user as never;
      session.apiToken = token.apiToken;
      return session;
    },
  },
});
