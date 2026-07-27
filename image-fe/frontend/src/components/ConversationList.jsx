export default function ConversationList({ character, conversations, onSelect, onNew, onDelete, onBack }) {
  return (
    <div className="conv-list">
      <button type="button" className="back-link" onClick={onBack}>
        ← Characters
      </button>
      <h2>{character.name}</h2>
      <button type="button" onClick={onNew}>
        + New chat
      </button>

      {!conversations.length && <p className="empty">No conversations yet — start one above.</p>}

      <ul className="conv-items">
        {conversations.map((c) => (
          <li key={c.id}>
            <button type="button" className="conv-item" onClick={() => onSelect(c)}>
              {c.title || character.name}
              <span className="conv-date">{new Date(c.created_at).toLocaleString()}</span>
            </button>
            <button type="button" className="danger small" onClick={() => onDelete(c)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
