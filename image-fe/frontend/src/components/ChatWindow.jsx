import { useEffect, useRef, useState } from "react";
import Avatar from "./Avatar";
import MessageText from "./MessageText";

export default function ChatWindow({ character, messages, streamingText, onEditMessage, onDeleteMessage, onAvatarClick }) {
  const endRef = useRef(null);
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streamingText]);

  const startEdit = (m) => {
    setEditingId(m.id);
    setEditText(m.content);
  };

  const cancelEdit = () => setEditingId(null);

  const saveEdit = () => {
    onEditMessage(editingId, editText);
    setEditingId(null);
  };

  const renderBody = (m) =>
    editingId === m.id ? (
      <div className="msg-edit-row">
        <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={3} autoFocus />
        <div className="msg-edit-buttons">
          <button type="button" onClick={saveEdit}>
            Save
          </button>
          <button type="button" onClick={cancelEdit}>
            Cancel
          </button>
        </div>
      </div>
    ) : (
      <>
        <p>
          <MessageText text={m.content} />
        </p>
        <div className="msg-hover-buttons">
          <button type="button" className="msg-edit-btn" onClick={() => startEdit(m)}>
            Edit
          </button>
          <button type="button" className="msg-edit-btn msg-delete-btn" onClick={() => onDeleteMessage(m.id)}>
            Delete
          </button>
        </div>
      </>
    );

  return (
    <div className="chat-window">
      {messages.map((m) =>
        m.role === "user" ? (
          <div key={m.id} className="bubble user">
            <span className="bubble-author">You</span>
            {renderBody(m)}
          </div>
        ) : (
          <div key={m.id} className="message-row">
            <Avatar character={character} size={32} onClick={() => onAvatarClick(character)} />
            <div className="bubble assistant">
              <span className="bubble-author">{character.name}</span>
              {renderBody(m)}
            </div>
          </div>
        )
      )}
      {streamingText !== null && (
        <div className="message-row">
          <Avatar character={character} size={32} onClick={() => onAvatarClick(character)} />
          <div className="bubble assistant streaming">
            <span className="bubble-author">{character.name}</span>
            <p>{streamingText ? <MessageText text={streamingText} /> : "…"}</p>
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
