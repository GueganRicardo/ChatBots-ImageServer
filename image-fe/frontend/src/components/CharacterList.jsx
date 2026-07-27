import Avatar from "./Avatar";

export default function CharacterList({ characters, onSelect, onNew, onImport, onEdit, onDelete, onAvatarClick }) {
  return (
    <div className="char-list">
      <div className="char-list-actions">
        <button type="button" onClick={onNew}>
          + New character
        </button>
        <button type="button" onClick={onImport}>
          Import card
        </button>
      </div>

      {!characters.length && (
        <p className="empty">No characters yet — create one or import a card to get started.</p>
      )}

      <div className="char-grid">
        {characters.map((c) => (
          <div className="char-card" key={c.id}>
            <div className="char-card-main" onClick={() => onSelect(c)}>
              <Avatar
                character={c}
                size={40}
                onClick={(e) => {
                  e.stopPropagation();
                  onAvatarClick(c);
                }}
              />
              <div className="char-card-info">
                <h3>{c.name}</h3>
                <p>{c.description || c.personality || "No description"}</p>
              </div>
            </div>
            <div className="char-card-buttons">
              <button type="button" onClick={() => onEdit(c)}>
                Edit
              </button>
              <button type="button" className="danger" onClick={() => onDelete(c)}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
