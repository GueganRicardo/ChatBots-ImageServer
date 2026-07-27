export default function ContextMeter({ used, limit }) {
  if (!used || !limit) return null;

  const pct = Math.min(100, Math.round((used / limit) * 100));
  const level = pct >= 90 ? "danger" : pct >= 70 ? "warning" : "ok";

  return (
    <div className={`context-meter ${level}`} title="Tokens used in the last request, out of the model's context window">
      <div className="context-meter-bar">
        <div className="context-meter-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="context-meter-label">
        {used.toLocaleString()} / {limit.toLocaleString()} tokens ({pct}%)
      </span>
    </div>
  );
}
