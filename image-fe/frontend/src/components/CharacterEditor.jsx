import { useEffect, useState } from "react";
import Avatar from "./Avatar";

const EMPTY = {
  name: "",
  description: "",
  personality: "",
  scenario: "",
  first_mes: "",
  mes_example: "",
  avatar: "",
};

export default function CharacterEditor({ initial, onSave, onCancel }) {
  const [char, setChar] = useState(initial || EMPTY);
  const [avatarFile, setAvatarFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const set = (key) => (e) => setChar((c) => ({ ...c, [key]: e.target.value }));

  useEffect(() => {
    if (!avatarFile) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  const onAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (file) setAvatarFile(file);
  };

  const submit = (e) => {
    e.preventDefault();
    if (!char.name.trim()) return;
    onSave(char, avatarFile);
  };

  return (
    <form className="char-editor" onSubmit={submit}>
      <h2>{initial ? "Edit character" : "New character"}</h2>

      <label>
        Profile picture
        <div className="avatar-upload-row">
          <Avatar character={previewUrl ? { avatar: previewUrl, name: char.name } : char} size={56} />
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onAvatarChange} />
        </div>
      </label>

      <label>
        Name
        <input value={char.name} onChange={set("name")} required />
      </label>

      <label>
        Description
        <textarea value={char.description} onChange={set("description")} rows={2} />
      </label>

      <label>
        Personality
        <textarea value={char.personality} onChange={set("personality")} rows={2} />
      </label>

      <label>
        Scenario
        <textarea value={char.scenario} onChange={set("scenario")} rows={2} />
      </label>

      <label>
        First message (opening line, sent as the character's first turn)
        <textarea value={char.first_mes} onChange={set("first_mes")} rows={2} />
      </label>

      <label>
        Example dialogue
        <textarea value={char.mes_example} onChange={set("mes_example")} rows={3} />
      </label>

      <div className="char-editor-buttons">
        <button type="submit">Save</button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
