const COLUMNS: Array<{ title: string; links: Array<{ label: string; badge?: string }> }> = [
  {
    title: "Product",
    links: [
      { label: "Overview" },
      { label: "Features" },
      { label: "Solutions", badge: "New" },
      { label: "Tutorials" },
      { label: "Pricing" },
      { label: "Releases" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About us" },
      { label: "Careers" },
      { label: "Press" },
      { label: "News" },
      { label: "Media kit" },
      { label: "Contact" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Blog" },
      { label: "Newsletter" },
      { label: "Events" },
      { label: "Help centre" },
      { label: "Tutorials" },
      { label: "Support" },
    ],
  },
  {
    title: "Social",
    links: [
      { label: "Twitter" },
      { label: "LinkedIn" },
      { label: "Facebook" },
      { label: "GitHub" },
      { label: "AngelList" },
      { label: "Dribbble" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms" },
      { label: "Privacy" },
      { label: "Cookies" },
      { label: "Licenses" },
      { label: "Settings" },
      { label: "Contact" },
    ],
  },
];

const SOCIAL_ICONS = ["𝕏", "in", "f", "gh", "d"];

export default function Footer() {
  return (
    <footer className="relative overflow-hidden pt-20">
      <div className="mx-auto grid max-w-[1000px] grid-cols-2 gap-8 px-6 sm:grid-cols-5 sm:px-10">
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h3 className="text-[12.5px] font-semibold text-accent">{col.title}</h3>
            <ul className="mt-4 flex flex-col gap-3">
              {col.links.map((link) => (
                <li key={link.label}>
                  <a
                    href="#"
                    className="inline-flex items-center gap-1.5 text-[13px] text-ink-secondary hover:text-ink"
                  >
                    {link.label}
                    {link.badge ? (
                      <span className="rounded-pill bg-accent px-1.5 py-0.5 text-[9px] font-semibold text-white">
                        {link.badge}
                      </span>
                    ) : null}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="relative z-10 mx-auto mt-16 flex max-w-[1000px] items-center justify-between border-t border-border px-6 py-6 sm:px-10">
        <span className="text-[12.5px] text-ink-muted">© 2026 Accurate. All rights reserved.</span>
        <div className="flex items-center gap-4 text-[13px] text-ink-secondary">
          {SOCIAL_ICONS.map((icon) => (
            <a key={icon} href="#" className="hover:text-ink">
              {icon}
            </a>
          ))}
        </div>
      </div>

      <div className="glow-footer pointer-events-none absolute inset-x-0 bottom-0 h-[280px]" />
      <div className="relative flex justify-center overflow-hidden">
        <div className="flex translate-y-[28%] items-center gap-3">
          <span className="mb-6 h-4 w-4 rounded-full bg-accent" />
          <span className="select-none font-serif text-[140px] font-semibold leading-none tracking-tight text-ink sm:text-[220px]">
            Accurate
          </span>
        </div>
      </div>
    </footer>
  );
}
