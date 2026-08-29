// The "AI Accurate Globe" icon (V0.3 Figma design): 3 exported layers
// stacked (warm background glow, blurred gradient blob, white ring glow)
// plus the white "A" glyph on top. `size` scales all four proportionally --
// the Figma design uses 112.5px for the empty-state hero and 34px for the
// inline "N sources reused" receipt line.
export default function AiOrb({ size = 112.5 }: { size?: number }) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <img
        src="/icons/orb-background.png"
        alt=""
        className="absolute inset-0 h-full w-full rounded-full object-cover"
      />
      <img
        src="/icons/orb-gradient.svg"
        alt=""
        className="absolute inset-0 h-full w-full rounded-full object-cover"
      />
      <img
        src="/icons/orb-ring.svg"
        alt=""
        className="absolute inset-0 h-full w-full object-cover"
      />
      <img
        src="/icons/orb-glyph.svg"
        alt=""
        className="absolute left-1/2 top-1/2 w-[43%] -translate-x-1/2 -translate-y-1/2"
      />
    </div>
  );
}
