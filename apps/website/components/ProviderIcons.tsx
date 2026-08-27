// Generic, monochrome marks for the "compatible with +100 LLMs" strip --
// abstract shapes evoking the variety of provider logos without tracing any
// specific company's trademarked mark.
const ICONS: Array<{ id: string; path: string }> = [
  {
    id: "blob",
    path: "M8 2.2c1.8-.3 3.4.6 4.4 2 .9 1.2 1.4 2.8 1 4.3-.4 1.6-1.7 2.8-3.1 3.6-1.5.8-3.3 1.1-4.8.4-1.5-.7-2.4-2.2-2.7-3.8-.3-1.6.1-3.4 1.2-4.6C5 2.8 6.4 2.5 8 2.2Z",
  },
  {
    id: "flower",
    path: "M8 8c0-2 1-3.6 2.6-4.6-.4 1.9-.2 3.6.9 5-1.9-.4-3.5.1-4.6 1.6.6-1.9.4-3.6-1-5C7 3.7 8 5.6 8 8Zm0 0c1.9.4 3.1 1.7 3.7 3.5-1.8-.7-3.5-.6-5 .6.9-1.8.9-3.5-.1-5.1.5 1.9 1.3 3 .4 1Zm0 0C6.1 8.4 4.9 9.7 4.3 11.5c.3-1.9-.1-3.5-1.6-4.6 1.9.4 3.5-.1 4.6-1.4C6.6 6.9 6.9 7.5 8 8Z",
  },
  {
    id: "spark",
    path: "M8 1.5c.4 2.6 1.1 4.1 2.5 5.1 1.1.8 2.4 1 4 1.4-1.6.4-2.9.6-4 1.4-1.4 1-2.1 2.5-2.5 5.1-.4-2.6-1.1-4.1-2.5-5.1-1.1-.8-2.4-1-4-1.4 1.6-.4 2.9-.6 4-1.4C6.9 5.6 7.6 4.1 8 1.5Z",
  },
  {
    id: "gem",
    path: "M4.5 3.5h7L14 7l-6 8.5L2 7l2.5-3.5Zm0 0L6 7m4-3.5L10 7M2 7h12M6 7l2 8.5L10 7",
  },
  {
    id: "wave",
    path: "M2 9.5c1.5-3.5 3.5-5.5 5.5-5.5 1.6 0 2.4 1.5 3.6 1.5 1 0 1.6-.9 2.9-1-1.3 3-3.3 6.5-6 6.5-1.7 0-2.6-1.6-3.9-1.6-1 0-1.5.7-2.1 1.5Z",
  },
];

export default function ProviderIcons() {
  return (
    <span className="flex items-center -space-x-1.5">
      {ICONS.map((icon) => (
        <span
          key={icon.id}
          className="flex h-6 w-6 items-center justify-center rounded-full border border-border bg-page"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d={icon.path} fill="#a39d92" stroke="#a39d92" strokeWidth="0.4" strokeLinejoin="round" />
          </svg>
        </span>
      ))}
    </span>
  );
}
