import { useEffect, useState } from "react";

export default function SummaryPanel({ draft, streaming, partial, uptoMessageId, onSave, onCancel }) {
  const [text, setText] = useState(draft);

  useEffect(() => {
    if (streaming) setText(draft);
  }, [draft, streaming]);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal summary-panel" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onCancel}>
          ✕
        </button>

        <h2>Summarize conversation</h2>
        <p className="summary-note">
          {streaming
            ? "Generating summary…"
            : "Review and edit the summary below, then save. Everything summarized will no longer be sent to the AI as raw transcript."}
        </p>
        {!streaming && partial && (
          <p className="summary-note">
            The backlog was too long for one pass — this covers only the oldest part
            (up to message #{uptoMessageId}). Save it, then run Summarize again to
            continue where it left off.
          </p>
        )}

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          readOnly={streaming}
        />

        <div className="modal-buttons">
          <button type="button" disabled={streaming} onClick={() => onSave(text)}>
            Save
          </button>
          <button type="button" className="danger" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
