export default function Avatar({ character, size = 40, onClick }) {
  const style = { width: size, height: size, cursor: onClick ? "pointer" : undefined };

  if (character?.avatar) {
    return (
      <img src={character.avatar} alt={character.name} className="avatar-img" style={style} onClick={onClick} />
    );
  }

  return (
    <div className="char-avatar" style={style} onClick={onClick}>
      {(character?.name || "?").slice(0, 1).toUpperCase()}
    </div>
  );
}
