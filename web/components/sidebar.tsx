"use client";

import {
  BarChart3,
  Building2,
  FolderKanban,
  FileStack,
  Landmark,
  LayoutGrid,
  Layers,
  LogOut,
  Menu,
  MessageCircle,
  Tags,
  Users,
  X,
} from "lucide-react";
import { signOut } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { LanguageToggle } from "@/components/language-toggle";
import { LogoBlock } from "@/components/logo";
import { cn } from "@/components/ui";
import { Link, usePathname } from "@/i18n/navigation";
import type { NavItem } from "@/lib/nav";

const ICONS = {
  chat: MessageCircle,
  knowledge: Layers,
  board: LayoutGrid,
  municipality: Building2,
  department: FolderKanban,
  users: Users,
  departments: FolderKanban,
  stats: BarChart3,
  municipalities: Landmark,
  "kb-admin": FileStack,
  categories: Tags,
} as const;

function NavLinks({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  return (
    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
      {items.map((item) => {
        const Icon = ICONS[item.icon];
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.key}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium transition-colors",
              active
                ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" />
            <span className="truncate">{item.label ?? t(item.key as never)}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarFooter({
  userName,
  roleLabel,
  language,
}: {
  userName: string;
  roleLabel: string;
  language: "he" | "en";
}) {
  const t = useTranslations("nav");
  return (
    <div className="border-t border-sidebar-border p-4">
      <Link href="/profile" className="block hover:opacity-80">
        <p className="text-sm font-semibold text-foreground">{userName}</p>
        <p className="text-xs text-muted-foreground">{roleLabel}</p>
      </Link>
      <div className="mt-3 flex items-center justify-between">
        <LanguageToggle language={language} />
        {/* `redirectTo`, not v4's `callbackUrl`: next-auth v5 ignores the old
            option and falls back to its configured base URL, so a deployment
            whose NEXTAUTH_URL still says localhost sends the user there. */}
        <button
          onClick={() => signOut({ redirectTo: "/" })}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <LogOut className="size-4" />
          {t("signOut")}
        </button>
      </div>
    </div>
  );
}

export function Sidebar({
  items,
  userName,
  roleLabel,
  language,
}: {
  items: NavItem[];
  userName: string;
  roleLabel: string;
  language: "he" | "en";
}) {
  const t = useTranslations("nav");
  const [open, setOpen] = useState(false);

  const content = (onNavigate?: () => void) => (
    <>
      <div className="border-b border-sidebar-border p-4">
        <LogoBlock />
      </div>
      <NavLinks items={items} onNavigate={onNavigate} />
      <SidebarFooter userName={userName} roleLabel={roleLabel} language={language} />
    </>
  );

  return (
    <>
      {/* Desktop */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-e border-sidebar-border bg-sidebar md:flex">
        {content()}
      </aside>

      {/* Mobile top bar + drawer */}
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-sidebar-border bg-sidebar p-3 md:hidden">
        <LogoBlock />
        <button
          aria-label={t("openMenu")}
          onClick={() => setOpen(true)}
          className="rounded-lg p-2 text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <Menu className="size-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            aria-hidden
            className="absolute inset-0 bg-foreground/30"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 start-0 flex w-72 flex-col bg-sidebar shadow-xl">
            <button
              className="absolute end-3 top-4 rounded-lg p-1.5 text-sidebar-foreground hover:bg-sidebar-accent"
              onClick={() => setOpen(false)}
            >
              <X className="size-5" />
            </button>
            {content(() => setOpen(false))}
          </div>
        </div>
      )}
    </>
  );
}
