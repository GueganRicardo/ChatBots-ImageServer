import PresetSelector from "./PresetSelector";

export default function ChatInput({
  text,
  setText,
  settings,
  setSettings,
  models,
  presets,
  onPresetChange,
  onNewPreset,
  onEditPreset,
  onSend,
  onImpersonate,
  onSummarize,
  busy,
  impersonating,
  summarizing,
}) {
  const submit = (e) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  };

  const setNum = (key) => (e) => setSettings((s) => ({ ...s, [key]: Number(e.target.value) }));

  return (
    <form className="chat-input" onSubmit={submit}>
      <details>
        <summary>Advanced settings</summary>
        <div className="grid">
          <PresetSelector
            presets={presets}
            selectedId={settings.preset_id}
            onChange={onPresetChange}
            onNew={onNewPreset}
            onEdit={onEditPreset}
          />

          <label>
            Model
            <select
              value={settings.model}
              onChange={(e) => setSettings((s) => ({ ...s, model: e.target.value }))}
            >
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>

          <label>
            Temperature
            <input type="number" min="0" max="2" step="0.05" value={settings.temperature} onChange={setNum("temperature")} />
          </label>

          <label>
            Top P
            <input type="number" min="0" max="1" step="0.05" value={settings.top_p} onChange={setNum("top_p")} title="1.0 = disabled. Prefer Min P for tail-cutting." />
          </label>

          <label>
            Min P
            <input type="number" min="0" max="1" step="0.01" value={settings.min_p} onChange={setNum("min_p")} title="Drops tokens below this fraction of the top token's probability. 0.05 is a good default; 0 = disabled." />
          </label>

          <label>
            Top K
            <input type="number" min="0" max="200" step="1" value={settings.top_k} onChange={setNum("top_k")} title="0 = disabled." />
          </label>

          <label>
            Repeat penalty
            <input type="number" min="0" max="2" step="0.05" value={settings.repeat_penalty} onChange={setNum("repeat_penalty")} title="Keep light (~1.05); heavy values degrade prose." />
          </label>

          <label>
            Repeat window
            <input type="number" min="0" max="8192" step="64" value={settings.repeat_last_n} onChange={setNum("repeat_last_n")} title="How many recent tokens the repeat/presence penalties look at (repeat_last_n). Large enough to cover whole replies fights loops." />
          </label>

          <label>
            Presence penalty
            <input type="number" min="0" max="2" step="0.05" value={settings.presence_penalty} onChange={setNum("presence_penalty")} title="Penalizes reusing tokens already present in the window. Helps against re-treading earlier phrasing." />
          </label>

          <label>
            Frequency penalty
            <input type="number" min="0" max="2" step="0.05" value={settings.frequency_penalty} onChange={setNum("frequency_penalty")} title="Penalizes tokens proportionally to how often they already appeared." />
          </label>

          <label>
            Max tokens
            <input type="number" min="16" max="4096" step="16" value={settings.max_tokens} onChange={setNum("max_tokens")} />
          </label>

          <label>
            Context window
            <input type="number" min="2048" max="131072" step="2048" value={settings.num_ctx} onChange={setNum("num_ctx")} title="Tokens of history the model can see (num_ctx). Bigger = remembers more, uses more VRAM." />
          </label>

          <label className="seed-row">
            Your persona (optional)
            <input
              type="text"
              value={settings.persona}
              onChange={(e) => setSettings((s) => ({ ...s, persona: e.target.value }))}
              placeholder="Describe yourself to the character..."
            />
          </label>

          <label className="seed-row">
            Current scene (optional)
            <textarea
              rows={2}
              value={settings.scene_state}
              onChange={(e) => setSettings((s) => ({ ...s, scene_state: e.target.value }))}
              placeholder="Where the story stands right now — overrides the card's opening scenario. e.g. 'She has accepted the arrangement and no longer negotiates.'"
              title="Injected right before the reply is generated. Update it as the story progresses so the character doesn't reset to their opening attitude."
            />
          </label>
        </div>
      </details>

      <div className="chat-input-row">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          placeholder="Say something..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(e);
            }
          }}
        />
        <button
          type="button"
          className="impersonate-btn"
          disabled={busy || impersonating || summarizing}
          onClick={onImpersonate}
          title="Have the AI draft your next line"
        >
          {impersonating ? "…" : "Impersonate"}
        </button>
        <button
          type="button"
          className="summarize-btn"
          disabled={busy || impersonating || summarizing}
          onClick={onSummarize}
          title="Summarize the conversation so far to free up context"
        >
          {summarizing ? "…" : "Summarize"}
        </button>
        <button type="submit" disabled={busy || impersonating || summarizing}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </form>
  );
}
