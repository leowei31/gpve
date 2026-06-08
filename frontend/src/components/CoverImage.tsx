import { useState } from "react";

// REQ-008: always show *something*. RAWG lacks art for a couple of titles, and live URLs can
// 404 — in either case we fall back to a tasteful gradient tile with the game's initials
// instead of a broken image. Never fabricated, just a placeholder.
export default function CoverImage({
  src,
  alt,
  className = "",
}: {
  src: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const showImg = src && !failed;

  if (showImg) {
    return (
      // Fade the cover in once it decodes (no flash of a half-loaded image).
      <img
        src={src!}
        alt={alt}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
        className={`h-full w-full object-cover transition-opacity duration-500 ${
          loaded ? "opacity-100" : "opacity-0"
        } ${className}`}
      />
    );
  }

  const initials = alt
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  return (
    <div
      className={`flex h-full w-full items-center justify-center bg-gradient-to-br from-gp-panel to-gp-card ${className}`}
    >
      <span className="text-2xl font-black text-gp-line">{initials}</span>
    </div>
  );
}
