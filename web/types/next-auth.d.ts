import type { Role } from "@/lib/roles";

export interface AppUser {
  id: string;
  name: string | null;
  email: string;
  role: Role;
  municipalityId: string | null;
  departmentIds: string[];
  language: "he" | "en";
  digestEnabled: boolean;
}

declare module "next-auth" {
  interface Session {
    user: AppUser;
    apiToken: string;
  }

  interface User extends AppUser {
    apiToken: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    user: AppUser;
    apiToken: string;
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    user: AppUser;
    apiToken: string;
  }
}
