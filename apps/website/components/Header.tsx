export default function Header() {
  return (
    <header className="relative z-10 mx-auto flex max-w-[1200px] items-center justify-between px-6 py-8 sm:px-10">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo.svg" alt="Accurate" className="h-[21px] w-auto" />
      <button
        type="button"
        className="rounded-pill bg-dark px-5 py-2.5 text-[13.5px] font-semibold text-white transition-opacity hover:opacity-90"
      >
        Register
      </button>
    </header>
  );
}
