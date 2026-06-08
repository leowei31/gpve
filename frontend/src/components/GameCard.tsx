import CoverImage from "./CoverImage";

export default function GameCard({
  title,
  cover_url,
  genres,
  rating,
  footer,
}: {
  title: string;
  cover_url: string | null;
  genres: string[];
  rating: number | null;
  footer?: React.ReactNode;
}) {
  return (
    <div className="card group overflow-hidden hover:-translate-y-1 hover:border-gp-glow/30 hover:shadow-glow">
      <div className="relative aspect-[16/10] overflow-hidden">
        <CoverImage
          src={cover_url}
          alt={title}
          className="transition-transform duration-500 ease-out group-hover:scale-[1.07]"
        />
        {/* Gentle bottom scrim so the title chip reads on busy art. */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/40 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        {rating != null && (
          <span className="absolute right-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-gp-glow backdrop-blur-sm">
            ★ {rating.toFixed(1)}
          </span>
        )}
      </div>
      <div className="p-3">
        <h3 className="truncate text-sm font-semibold transition-colors group-hover:text-gp-glow" title={title}>
          {title}
        </h3>
        <p className="mt-0.5 truncate text-xs text-gp-muted">{genres.slice(0, 3).join(" · ") || "—"}</p>
        {footer}
      </div>
    </div>
  );
}
