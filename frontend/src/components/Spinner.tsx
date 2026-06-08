export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex animate-fade-in flex-col items-center justify-center gap-4 py-16 text-gp-muted">
      <span className="relative grid h-9 w-9 place-items-center">
        <span className="absolute inset-0 animate-spin rounded-full border-2 border-gp-line border-t-gp-glow" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gp-glow/70" />
      </span>
      {label && <p className="animate-pulse text-sm">{label}</p>}
    </div>
  );
}
