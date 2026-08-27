interface LogoMarkProps {
  size?: number;
  variant?: "default" | "hero";
  responsive?: boolean;
}

// `responsive` makes the mark fill its parent (100%) and scale type via
// container queries, instead of a fixed pixel size -- used for the large
// "where Accurate comes from" circle so it never overflows on mobile.
export default function LogoMark({ size = 64, variant = "default", responsive = false }: LogoMarkProps) {
  const isHero = variant === "hero";
  return (
    <div
      className={`relative flex shrink-0 items-center justify-center rounded-full ${isHero ? "orb-red-orange" : "glow-orb"} ${responsive ? "[container-type:inline-size]" : ""}`}
      style={responsive ? { width: "100%", height: "100%" } : { width: size, height: size }}
    >
      {isHero ? (
        <span
          className="absolute rounded-full bg-white"
          style={
            responsive
              ? { width: "14cqw", height: "14cqw", left: "18%", top: "26%" }
              : { width: size * 0.14, height: size * 0.14, left: "18%", top: "26%" }
          }
        />
      ) : null}
      <span
        className="font-serif font-semibold text-white"
        style={responsive ? { fontSize: "50cqw" } : { fontSize: size * 0.5 }}
      >
        A
      </span>
    </div>
  );
}
