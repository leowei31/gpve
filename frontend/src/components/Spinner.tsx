export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-gp-muted">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-gp-line border-t-gp-glow" />
      {label && <p className="text-sm">{label}</p>}
    </div>
  );
}
