export default function PromptForm({ form, setForm, options, onGenerate, busy }) {
  const set = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };
  const setNum = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const loras = form.loras || [];
  const loraSelected = (name) => loras.some((l) => l.name === name);
  const toggleLora = (name) => (e) => {
    const checked = e.target.checked;
    setForm((f) => ({
      ...f,
      loras: checked
        ? [...(f.loras || []), { name, strength: 1.0 }]
        : (f.loras || []).filter((l) => l.name !== name),
    }));
  };
  const setLoraStrength = (name) => (e) => {
    const strength = e.target.value;
    setForm((f) => ({
      ...f,
      loras: (f.loras || []).map((l) => (l.name === name ? { ...l, strength } : l)),
    }));
  };

  const submit = (e) => {
    e.preventDefault();
    if (!form.prompt.trim() || busy) return;
    onGenerate({
      ...form,
      width: Number(form.width),
      height: Number(form.height),
      steps: Number(form.steps),
      cfg: Number(form.cfg),
      denoise: Number(form.denoise),
      batch_size: Number(form.batch_size),
      seed: Number(form.seed) || 0,
      loras: loras.map((l) => ({ name: l.name, strength: Number(l.strength) || 0 })),
    });
  };

  return (
    <form className="prompt-form" onSubmit={submit}>
      <label>
        Prompt
        <textarea
          value={form.prompt}
          onChange={set("prompt")}
          rows={3}
          placeholder="A cinematic photo of..."
          required
        />
      </label>

      <label>
        Negative prompt
        <textarea value={form.negative_prompt} onChange={set("negative_prompt")} rows={2} />
      </label>

      {(options.loras || []).length > 0 && (
        <fieldset className="lora-picker">
          <legend>LoRAs</legend>
          {options.loras.map((name) => {
            const active = loraSelected(name);
            const entry = loras.find((l) => l.name === name);
            return (
              <div key={name} className="lora-row">
                <span className="checkbox-inline">
                  <input type="checkbox" checked={active} onChange={toggleLora(name)} />
                  {name}
                </span>
                {active && (
                  <input
                    type="number"
                    min="-2"
                    max="2"
                    step="0.05"
                    value={entry.strength}
                    onChange={setLoraStrength(name)}
                    title="LoRA strength"
                  />
                )}
              </div>
            );
          })}
        </fieldset>
      )}

      <details>
        <summary>Advanced settings</summary>
        <div className="grid">
          <label>
            Model
            <select value={form.model} onChange={set("model")}>
              {options.checkpoints.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>

          <label>
            Width
            <input type="number" min="64" step="8" value={form.width} onChange={setNum("width")} />
          </label>

          <label>
            Height
            <input type="number" min="64" step="8" value={form.height} onChange={setNum("height")} />
          </label>

          <label>
            Steps
            <input type="number" min="1" max="150" value={form.steps} onChange={setNum("steps")} />
          </label>

          <label>
            CFG
            <input type="number" min="0" max="30" step="0.5" value={form.cfg} onChange={setNum("cfg")} />
          </label>

          <label>
            Sampler
            <select value={form.sampler_name} onChange={set("sampler_name")}>
              {options.samplers.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <label>
            Scheduler
            <select value={form.scheduler} onChange={set("scheduler")}>
              {options.schedulers.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <label>
            Denoise
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={form.denoise}
              onChange={setNum("denoise")}
            />
          </label>

          <label>
            Batch size
            <input
              type="number"
              min="1"
              max="8"
              value={form.batch_size}
              onChange={setNum("batch_size")}
            />
          </label>

          <label className="seed-row">
            Seed
            <input
              type="number"
              value={form.seed}
              onChange={setNum("seed")}
              disabled={form.randomize_seed}
            />
            <span className="checkbox-inline">
              <input type="checkbox" checked={form.randomize_seed} onChange={set("randomize_seed")} />
              Randomize
            </span>
          </label>
        </div>
      </details>

      <button type="submit" disabled={busy}>
        {busy ? "Generating…" : "Generate"}
      </button>
    </form>
  );
}
