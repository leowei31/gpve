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
    <div className="card group overflow-hidden transition hover:border-gp-glow/40 hover:shadow-glow">
      <div className="relative aspect-[16/10] overflow-hidden">
        <CoverImage src={cover_url} alt={title} className="transition duration-300 group-hover:scale-105" />
        {rating != null && (
          <span className="absolute right-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-gp-glow">
            ★ {rating.toFixed(1)}
          </span>
        )}
      </div>
      <div className="p-3">
        <h3 className="truncate text-sm font-semibold" title={title}>
          {title}
        </h3>
        <p className="mt-0.5 truncate text-xs text-gp-muted">{genres.slice(0, 3).join(" · ") || "—"}</p>
        {footer}
      </div>
    </div>
  );
}
