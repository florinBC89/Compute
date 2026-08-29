import { signOut } from "@/app/actions";

// The sidebar nav from the V0.3 Figma design ("Registered user" flow).
// Only "New" (start a fresh conversation) is functional today -- the
// others (Project/Reports/Overview/Support) have no backing page yet, so
// they render as static labels rather than dead links. The account row
// doubles as sign-out, since the design has no separate control for it.
const NAV_ITEMS = [
  { href: "/", label: "New", icon: "/icons/nav-new.svg" },
  { href: null, label: "Project", icon: "/icons/nav-chart.svg" },
  { href: null, label: "Reports", icon: "/icons/nav-reports.svg" },
  { href: null, label: "Overview", icon: "/icons/nav-chart.svg" },
] as const;

function displayName(email: string): string {
  const local = email.split("@")[0] ?? email;
  return local.charAt(0).toUpperCase() + local.slice(1);
}

export default function Sidebar({ email }: { email: string }) {
  const name = displayName(email);

  return (
    <aside className="flex h-screen w-[179px] shrink-0 flex-col justify-between bg-chat-warm">
      <div>
        <div className="px-5 pb-6 pt-8">
          <img src="/logo.svg" alt="Accurate" className="h-[19px] w-auto" />
        </div>
        <nav className="flex flex-col gap-0.5 px-4">
          {NAV_ITEMS.map((item) =>
            item.href ? (
              <a
                key={item.label}
                href={item.href}
                className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[16px] text-chat-ink hover:bg-white/50"
              >
                <img src={item.icon} alt="" className="h-5 w-5" />
                {item.label}
              </a>
            ) : (
              <span
                key={item.label}
                className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[16px] text-chat-ink opacity-60"
              >
                <img src={item.icon} alt="" className="h-5 w-5" />
                {item.label}
              </span>
            )
          )}
        </nav>
      </div>

      <div className="flex flex-col gap-6 px-4 pb-[26px]">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2 px-3 py-2 text-[16px] text-chat-ink opacity-60">
            <img src="/icons/nav-support.svg" alt="" className="h-5 w-5" />
            Support
          </span>
          <span className="flex items-center gap-2 px-3 py-2 text-[16px] text-chat-ink opacity-60">
            <img src="/icons/nav-settings.svg" alt="" className="h-5 w-5" />
            Settings
          </span>
        </div>
        <form action={signOut}>
          <button
            type="submit"
            title="Sign out"
            className="flex items-center gap-2 pl-2 pr-8 pt-6 text-[14px] font-medium text-chat-ink"
          >
            <span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-white">
              {name.charAt(0)}
            </span>
            {name}
          </button>
        </form>
      </div>
    </aside>
  );
}
