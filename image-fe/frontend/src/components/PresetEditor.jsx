import { useState } from "react";

const EMPTY = {
  name: "",
  system_prompt: "",
  post_history_instructions: "",
  impersonation_prompt: "",
  temperature: 1.0,
  top_p: 1.0,
  min_p: 0.05,
  top_k: 0,
  repeat_penalty: 1.05,
  repeat_last_n: 2048,
  presence_penalty: 0.5,
  frequency_penalty: 0.0,
  max_tokens: 512,
  model: "",
};

// Presets saved before the newer sampler fields existed carry NULLs for them; fill
// those from EMPTY so the number inputs stay controlled.
function withDefaults(initial) {
  if (!initial) return EMPTY;
  const clean = Object.fromEntries(
    Object.entries(initial).filter(([, v]) => v !== null && v !== undefined)
  );
  return { ...EMPTY, ...clean };
}

export default function PresetEditor({ initial, onSave, onCancel, onDelete }) {
  const [preset, setPreset] = useState(withDefaults(initial));
  const set = (key) => (e) => setPreset((p) => ({ ...p, [key]: e.target.value }));
  const setNum = (key) => (e) => setPreset((p) => ({ ...p, [key]: Number(e.target.value) }));

  const submit = (e) => {
    e.preventDefault();
    if (!preset.name.trim()) return;
    onSave(preset);
  };

  return (
    <form className="char-editor" onSubmit={submit}>
      <h2>{initial ? "Edit preset" : "New preset"}</h2>

      <label>
        Name
        <input value={preset.name} onChange={set("name")} required />
      </label>

      <label>
        Pre-history instructions (sent before the conversation — tone, genre, style, rules)
        <textarea value={preset.system_prompt} onChange={set("system_prompt")} rows={3} />
      </label>

      <label>
        Post-history instructions (reinforced right before every reply — good for hard rules)
        <textarea
          value={preset.post_history_instructions}
          onChange={set("post_history_instructions")}
          rows={2}
        />
      </label>

      <label>
        Impersonation prompt (used by the "Impersonate" button; supports {"{{user}}"} /{" "}
        {"{{char}}"} placeholders)
        <textarea
          value={preset.impersonation_prompt}
          onChange={set("impersonation_prompt")}
          rows={2}
        />
      </label>

      <div className="grid">
        <label>
          Model override (blank = keep current)
          <input value={preset.model} onChange={set("model")} placeholder="(use selected model)" />
        </label>
        <label>
          Temperature
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            value={preset.temperature}
            onChange={setNum("temperature")}
          />
        </label>
        <label>
          Top P
          <input
            type="number"
            min="0"
            max="1"
            step="0.05"
            value={preset.top_p}
            onChange={setNum("top_p")}
            title="1.0 = disabled. Prefer Min P for tail-cutting."
          />
        </label>
        <label>
          Min P
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={preset.min_p}
            onChange={setNum("min_p")}
            title="Drops tokens below this fraction of the top token's probability. 0 = disabled."
          />
        </label>
        <label>
          Top K
          <input
            type="number"
            min="0"
            max="200"
            step="1"
            value={preset.top_k}
            onChange={setNum("top_k")}
            title="0 = disabled."
          />
        </label>
        <label>
          Repeat penalty
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            value={preset.repeat_penalty}
            onChange={setNum("repeat_penalty")}
            title="Keep light (~1.05); heavy values degrade prose."
          />
        </label>
        <label>
          Repeat window
          <input
            type="number"
            min="0"
            max="8192"
            step="64"
            value={preset.repeat_last_n}
            onChange={setNum("repeat_last_n")}
            title="How many recent tokens the penalties look at (repeat_last_n)."
          />
        </label>
        <label>
          Presence penalty
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            value={preset.presence_penalty}
            onChange={setNum("presence_penalty")}
            title="Penalizes reusing tokens already present in the window."
          />
        </label>
        <label>
          Frequency penalty
          <input
            type="number"
            min="0"
            max="2"
            step="0.05"
            value={preset.frequency_penalty}
            onChange={setNum("frequency_penalty")}
            title="Penalizes tokens proportionally to how often they already appeared."
          />
        </label>
        <label>
          Max tokens
          <input
            type="number"
            min="16"
            max="4096"
            step="16"
            value={preset.max_tokens}
            onChange={setNum("max_tokens")}
          />
        </label>
      </div>

      <div className="char-editor-buttons">
        <button type="submit">Save</button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
        {initial && onDelete && (
          <button type="button" className="danger" onClick={() => onDelete(initial)}>
            Delete
          </button>
        )}
      </div>
    </form>
  );
}
