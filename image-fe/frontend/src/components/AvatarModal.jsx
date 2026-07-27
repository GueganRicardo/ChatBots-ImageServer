export default function AvatarModal({ character, onClose }) {
  if (!character) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal avatar-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>
          ✕
        </button>
        {character.avatar ? (
          <img src={character.avatar} alt={character.name} className="avatar-modal-img" />
        ) : (
          <div className="char-avatar avatar-modal-fallback">{character.name.slice(0, 1).toUpperCase()}</div>
        )}
        <p className="avatar-modal-name">{character.name}</p>
      </div>
    </div>
  );
}
