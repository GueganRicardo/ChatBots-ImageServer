import { useState } from "react";

export default function CharacterImport({ onImport, onCancel }) {
  const [text, setText] = useState("");
  const [error, setError] = useState(null);

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setText(await file.text());
  };

  const submit = (e) => {
    e.preventDefault();
    try {
      const card = JSON.parse(text);
      setError(null);
      onImport(card);
    } catch {
      setError("That doesn't look like valid JSON.");
    }
  };

  return (
    <form className="char-editor" onSubmit={submit}>
      <h2>Import character card</h2>
      <p className="hint">
        Paste a SillyTavern/Chub v2 character card JSON, or upload a <code>.json</code> file
        exported from one of those tools.
      </p>
      <label>
        <input type="file" accept=".json,application/json" onChange={onFile} />
      </label>
      <label>
        Card JSON
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder='{"spec": "chara_card_v2", "data": {"name": "...", ...}}'
        />
      </label>
      {error && <div className="error">{error}</div>}
      <div className="char-editor-buttons">
        <button type="submit">Import</button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
