export default function LogoMark({ size = 64 }: { size?: number }) {
  return (
    <div
      className="glow-orb flex shrink-0 items-center justify-center rounded-full"
      style={{ width: size, height: size }}
    >
      <span
        className="font-serif font-semibold italic text-white"
        style={{ fontSize: size * 0.42 }}
      >
        A
      </span>
    </div>
  );
}
