export default function PresetSelector({ presets, selectedId, onChange, onNew, onEdit }) {
  const selected = presets.find((p) => p.id === selectedId) || null;

  return (
    <div className="preset-row">
      <label>
        Preset
        <select
          value={selectedId ?? ""}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">(none)</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <div className="preset-row-buttons">
        <button type="button" onClick={onNew}>
          + New
        </button>
        <button type="button" disabled={!selected} onClick={() => selected && onEdit(selected)}>
          Edit
        </button>
      </div>
    </div>
  );
}
