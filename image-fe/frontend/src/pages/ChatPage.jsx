import { useCallback, useEffect, useState } from "react";
import CharacterList from "../components/CharacterList";
import CharacterEditor from "../components/CharacterEditor";
import CharacterImport from "../components/CharacterImport";
import ConversationList from "../components/ConversationList";
import ChatWindow from "../components/ChatWindow";
import ChatInput from "../components/ChatInput";
import PresetEditor from "../components/PresetEditor";
import ContextMeter from "../components/ContextMeter";
import SummaryPanel from "../components/SummaryPanel";
import AvatarModal from "../components/AvatarModal";
import {
  createCharacter,
  createConversation,
  createPreset,
  deleteCharacter,
  deleteConversation,
  deleteMessage,
  deletePreset,
  getChatDefaults,
  getChatModels,
  getCharacters,
  getConversation,
  getConversations,
  getPresets,
  importCharacter,
  impersonate,
  saveSummary,
  sendChatMessage,
  streamChat,
  summarizeConversation,
  updateCharacter,
  updateMessage,
  updatePreset,
  uploadCharacterAvatar,
} from "../api";

// Applies a preset's bundled generation defaults onto a settings object. A blank
// preset.model means "keep whatever model is currently selected". `??` fallbacks:
// presets saved before the newer sampler fields existed store NULL for them.
function applyPreset(base, preset) {
  if (!preset) return { ...base, preset_id: null };
  return {
    ...base,
    preset_id: preset.id,
    temperature: preset.temperature ?? base.temperature,
    top_p: preset.top_p ?? base.top_p,
    min_p: preset.min_p ?? base.min_p,
    top_k: preset.top_k ?? base.top_k,
    repeat_penalty: preset.repeat_penalty ?? base.repeat_penalty,
    repeat_last_n: preset.repeat_last_n ?? base.repeat_last_n,
    presence_penalty: preset.presence_penalty ?? base.presence_penalty,
    frequency_penalty: preset.frequency_penalty ?? base.frequency_penalty,
    max_tokens: preset.max_tokens ?? base.max_tokens,
    model: preset.model || base.model,
  };
}

export default function ChatPage() {
  const [view, setView] = useState("characters"); // characters | conversations | chat
  const [characters, setCharacters] = useState([]);
  const [presets, setPresets] = useState([]);
  const [models, setModels] = useState([]);
  const [settings, setSettings] = useState(null); // chat defaults + persona + preset_id

  const [editorState, setEditorState] = useState(null); // null | "new" | "import" | character
  const [presetEditorState, setPresetEditorState] = useState(null); // null | "new" | preset
  const [selectedCharacter, setSelectedCharacter] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [streamingText, setStreamingText] = useState(null);
  const [busy, setBusy] = useState(false);
  const [impersonating, setImpersonating] = useState(false);
  const [error, setError] = useState(null);
  const [contextUsage, setContextUsage] = useState(null); // {used, limit} | null
  const [summarizing, setSummarizing] = useState(false);
  const [summaryDraft, setSummaryDraft] = useState(null); // {text, uptoMessageId} | null
  const [enlargedAvatar, setEnlargedAvatar] = useState(null); // character | null

  const refreshCharacters = useCallback(async () => {
    setCharacters(await getCharacters());
  }, []);

  const refreshPresets = useCallback(async () => {
    const list = await getPresets();
    setPresets(list);
    return list;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [chars, presetList, defaults, modelList] = await Promise.all([
          getCharacters(),
          getPresets(),
          getChatDefaults(),
          getChatModels(),
        ]);
        setCharacters(chars);
        setPresets(presetList);
        setModels(modelList.models.length ? modelList.models : [defaults.model]);
        // Zero-config UX: auto-apply the designated default preset (by name, from
        // /api/chat/defaults), falling back to the first preset if it was deleted.
        const defaultPreset =
          presetList.find((p) => p.name === defaults.default_preset) || presetList[0] || null;
        setSettings(
          applyPreset(
            { ...defaults, persona: defaults.persona || "", scene_state: "" },
            defaultPreset
          )
        );
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  // ------------------------------------------------------------ characters

  const handleSelectCharacter = useCallback(async (char) => {
    setError(null);
    setSelectedCharacter(char);
    try {
      setConversations(await getConversations(char.id));
      setView("conversations");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const handleSaveCharacter = useCallback(
    async (char, avatarFile) => {
      try {
        let saved;
        if (editorState && editorState !== "new" && editorState !== "import") {
          saved = await updateCharacter(editorState.id, char);
        } else {
          saved = await createCharacter(char);
        }
        if (avatarFile) {
          saved = await uploadCharacterAvatar(saved.id, avatarFile);
        }
        setEditorState(null);
        await refreshCharacters();
        setSelectedCharacter((c) => (c && c.id === saved.id ? saved : c));
      } catch (e) {
        setError(String(e));
      }
    },
    [editorState, refreshCharacters]
  );

  const handleImportCharacter = useCallback(
    async (card) => {
      try {
        await importCharacter(card);
        setEditorState(null);
        await refreshCharacters();
      } catch (e) {
        setError(String(e));
      }
    },
    [refreshCharacters]
  );

  const handleDeleteCharacter = useCallback(
    async (char) => {
      if (!window.confirm(`Delete "${char.name}"? This also deletes its conversations.`)) return;
      try {
        await deleteCharacter(char.id);
        await refreshCharacters();
      } catch (e) {
        setError(String(e));
      }
    },
    [refreshCharacters]
  );

  // ------------------------------------------------------------- presets

  const handleSavePreset = useCallback(
    async (preset) => {
      try {
        let saved;
        if (presetEditorState && presetEditorState !== "new") {
          saved = await updatePreset(presetEditorState.id, preset);
        } else {
          saved = await createPreset(preset);
        }
        setPresetEditorState(null);
        await refreshPresets();
        setSettings((s) => applyPreset(s, saved));
      } catch (e) {
        setError(String(e));
      }
    },
    [presetEditorState, refreshPresets]
  );

  const handleDeletePreset = useCallback(
    async (preset) => {
      if (!window.confirm(`Delete preset "${preset.name}"?`)) return;
      try {
        await deletePreset(preset.id);
        setPresetEditorState(null);
        const list = await refreshPresets();
        // If the deleted preset was selected, fall back to the default preset
        // (its name rides along in settings via the /api/chat/defaults spread).
        setSettings((s) =>
          s.preset_id === preset.id
            ? applyPreset(s, list.find((p) => p.name === s.default_preset) || list[0] || null)
            : s
        );
      } catch (e) {
        setError(String(e));
      }
    },
    [refreshPresets]
  );

  const handlePresetChange = useCallback(
    (presetId) => {
      const preset = presets.find((p) => p.id === presetId) || null;
      setSettings((s) => applyPreset(s, preset));
    },
    [presets]
  );

  // --------------------------------------------------------- conversations

  const handleNewConversation = useCallback(async () => {
    try {
      const { conversation, messages: msgs } = await createConversation(
        selectedCharacter.id,
        "",
        settings.preset_id
      );
      setSelectedConversation(conversation);
      setMessages(msgs);
      setStreamingText(null);
      setText("");
      setContextUsage(null);
      // Scene state is per-conversation story state; never carry it into a fresh chat.
      setSettings((s) => ({ ...s, scene_state: "" }));
      setView("chat");
    } catch (e) {
      setError(String(e));
    }
  }, [selectedCharacter, settings]);

  const handleSelectConversation = useCallback(
    async (conv) => {
      try {
        const { conversation, messages: msgs } = await getConversation(conv.id);
        setSelectedConversation(conversation);
        setMessages(msgs);
        setStreamingText(null);
        setText("");
        setContextUsage(null);
        setSettings((s) => ({
          ...s,
          preset_id: conversation.preset_id ?? s.preset_id,
          temperature: conversation.temperature ?? s.temperature,
          top_p: conversation.top_p ?? s.top_p,
          min_p: conversation.min_p ?? s.min_p,
          top_k: conversation.top_k ?? s.top_k,
          repeat_penalty: conversation.repeat_penalty ?? s.repeat_penalty,
          repeat_last_n: conversation.repeat_last_n ?? s.repeat_last_n,
          presence_penalty: conversation.presence_penalty ?? s.presence_penalty,
          frequency_penalty: conversation.frequency_penalty ?? s.frequency_penalty,
          max_tokens: conversation.max_tokens ?? s.max_tokens,
          model: conversation.model || s.model,
          // `||` (not `??`): conversations saved before the persona default existed
          // store "" -- let those fall back to the default persona too.
          persona: conversation.persona || s.persona,
          // Story state belongs to THIS conversation only -- blank stays blank.
          scene_state: conversation.scene_state ?? "",
          num_ctx: conversation.num_ctx ?? s.num_ctx,
        }));
        setView("chat");
      } catch (e) {
        setError(String(e));
      }
    },
    []
  );

  const handleDeleteConversation = useCallback(
    async (conv) => {
      if (!window.confirm("Delete this conversation?")) return;
      try {
        await deleteConversation(conv.id);
        setConversations(await getConversations(selectedCharacter.id));
      } catch (e) {
        setError(String(e));
      }
    },
    [selectedCharacter]
  );

  // ---------------------------------------------------------------- chat

  const handleSend = useCallback(
    async (msg) => {
      setError(null);
      setBusy(true);
      setMessages((m) => [...m, { id: `local-${Date.now()}`, role: "user", content: msg }]);
      setStreamingText("");
      try {
        const { stream_id } = await sendChatMessage({
          conversation_id: selectedConversation.id,
          message: msg,
          persona: settings.persona,
          scene_state: settings.scene_state,
          preset_id: settings.preset_id,
          model: settings.model,
          temperature: settings.temperature,
          top_p: settings.top_p,
          min_p: settings.min_p,
          top_k: settings.top_k,
          repeat_penalty: settings.repeat_penalty,
          repeat_last_n: settings.repeat_last_n,
          presence_penalty: settings.presence_penalty,
          frequency_penalty: settings.frequency_penalty,
          max_tokens: settings.max_tokens,
          num_ctx: settings.num_ctx,
        });
        await streamChat(stream_id, {
          onToken: (chunk) => setStreamingText((t) => t + chunk),
          onDone: async (done) => {
            if (done.prompt_eval_count && done.num_ctx) {
              setContextUsage({ used: done.prompt_eval_count, limit: done.num_ctx });
            }
            try {
              const { messages: msgs } = await getConversation(selectedConversation.id);
              setMessages(msgs);
            } finally {
              setStreamingText(null);
              setBusy(false);
            }
          },
          onError: (msg2) => {
            setError(msg2);
            setStreamingText(null);
            setBusy(false);
          },
        });
      } catch (e) {
        setError(String(e));
        setStreamingText(null);
        setBusy(false);
      }
    },
    [selectedConversation, settings]
  );

  const handleImpersonate = useCallback(async () => {
    setError(null);
    setImpersonating(true);
    setText("");
    try {
      const { stream_id } = await impersonate({
        conversation_id: selectedConversation.id,
        persona: settings.persona,
        scene_state: settings.scene_state,
        preset_id: settings.preset_id,
        model: settings.model,
        temperature: settings.temperature,
        top_p: settings.top_p,
        min_p: settings.min_p,
        top_k: settings.top_k,
        repeat_penalty: settings.repeat_penalty,
        repeat_last_n: settings.repeat_last_n,
        presence_penalty: settings.presence_penalty,
        frequency_penalty: settings.frequency_penalty,
        max_tokens: settings.max_tokens,
        num_ctx: settings.num_ctx,
      });
      await streamChat(stream_id, {
        onToken: (chunk) => setText((t) => t + chunk),
        onDone: (done) => {
          if (done.prompt_eval_count && done.num_ctx) {
            setContextUsage({ used: done.prompt_eval_count, limit: done.num_ctx });
          }
          setImpersonating(false);
        },
        onError: (msg) => {
          setError(msg);
          setImpersonating(false);
        },
      });
    } catch (e) {
      setError(String(e));
      setImpersonating(false);
    }
  }, [selectedConversation, settings]);

  const handleEditMessage = useCallback(async (id, content) => {
    try {
      await updateMessage(id, content);
      setMessages((m) => m.map((x) => (x.id === id ? { ...x, content } : x)));
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const handleDeleteMessage = useCallback(async (id) => {
    if (!window.confirm("Delete this message? This can't be undone.")) return;
    try {
      await deleteMessage(id);
      setMessages((m) => m.filter((x) => x.id !== id));
    } catch (e) {
      setError(String(e));
    }
  }, []);

  // -------------------------------------------------------------- summarize

  const handleSummarize = useCallback(async () => {
    setError(null);
    setSummarizing(true);
    setSummaryDraft({ text: "", uptoMessageId: null, partial: false });
    try {
      const { stream_id, upto_message_id, partial } = await summarizeConversation({
        conversation_id: selectedConversation.id,
        model: settings.model,
      });
      await streamChat(stream_id, {
        onToken: (chunk) =>
          setSummaryDraft((d) => ({
            ...d,
            text: d.text + chunk,
            uptoMessageId: upto_message_id,
            partial: Boolean(partial),
          })),
        onDone: () => setSummarizing(false),
        onError: (msg) => {
          setError(msg);
          setSummarizing(false);
          setSummaryDraft(null);
        },
      });
    } catch (e) {
      setError(String(e));
      setSummarizing(false);
      setSummaryDraft(null);
    }
  }, [selectedConversation, settings]);

  const handleSaveSummary = useCallback(
    async (text) => {
      try {
        const conversation = await saveSummary(selectedConversation.id, {
          summary: text,
          upto_message_id: summaryDraft.uptoMessageId,
        });
        setSelectedConversation(conversation);
        setSummaryDraft(null);
      } catch (e) {
        setError(String(e));
      }
    },
    [selectedConversation, summaryDraft]
  );

  const handleCancelSummary = useCallback(() => {
    setSummaryDraft(null);
    setSummarizing(false);
  }, []);

  if (!settings) {
    return <div className="loading">Loading…</div>;
  }

  return (
    <div className="chat-page">
      {error && <div className="error">{error}</div>}

      {editorState === "new" && (
        <CharacterEditor onSave={handleSaveCharacter} onCancel={() => setEditorState(null)} />
      )}
      {editorState === "import" && (
        <CharacterImport onImport={handleImportCharacter} onCancel={() => setEditorState(null)} />
      )}
      {editorState && editorState !== "new" && editorState !== "import" && (
        <CharacterEditor
          initial={editorState}
          onSave={handleSaveCharacter}
          onCancel={() => setEditorState(null)}
        />
      )}

      {presetEditorState && (
        <PresetEditor
          initial={presetEditorState === "new" ? null : presetEditorState}
          onSave={handleSavePreset}
          onCancel={() => setPresetEditorState(null)}
          onDelete={handleDeletePreset}
        />
      )}

      {!editorState && !presetEditorState && view === "characters" && (
        <CharacterList
          characters={characters}
          onSelect={handleSelectCharacter}
          onNew={() => setEditorState("new")}
          onImport={() => setEditorState("import")}
          onEdit={setEditorState}
          onDelete={handleDeleteCharacter}
          onAvatarClick={setEnlargedAvatar}
        />
      )}

      {!editorState && !presetEditorState && view === "conversations" && selectedCharacter && (
        <ConversationList
          character={selectedCharacter}
          conversations={conversations}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          onBack={() => setView("characters")}
        />
      )}

      {!editorState && !presetEditorState && view === "chat" && selectedCharacter && selectedConversation && (
        <div className="chat-view">
          <button type="button" className="back-link" onClick={() => setView("conversations")}>
            ← {selectedCharacter.name}'s chats
          </button>
          {selectedConversation.summary_upto_message_id && (
            <p className="summary-note">
              Summarized up to message #{selectedConversation.summary_upto_message_id} — earlier
              turns are no longer sent to the AI as raw transcript.
            </p>
          )}
          <ChatWindow
            character={selectedCharacter}
            messages={messages}
            streamingText={streamingText}
            onEditMessage={handleEditMessage}
            onDeleteMessage={handleDeleteMessage}
            onAvatarClick={setEnlargedAvatar}
          />
          <ContextMeter used={contextUsage?.used} limit={contextUsage?.limit} />
          <ChatInput
            text={text}
            setText={setText}
            settings={settings}
            setSettings={setSettings}
            models={models}
            presets={presets}
            onPresetChange={handlePresetChange}
            onNewPreset={() => setPresetEditorState("new")}
            onEditPreset={setPresetEditorState}
            onSend={handleSend}
            onImpersonate={handleImpersonate}
            onSummarize={handleSummarize}
            busy={busy}
            impersonating={impersonating}
            summarizing={summarizing}
          />
        </div>
      )}

      {summaryDraft && (
        <SummaryPanel
          draft={summaryDraft.text}
          streaming={summarizing}
          partial={summaryDraft.partial}
          uptoMessageId={summaryDraft.uptoMessageId}
          onSave={handleSaveSummary}
          onCancel={handleCancelSummary}
        />
      )}

      <AvatarModal character={enlargedAvatar} onClose={() => setEnlargedAvatar(null)} />
    </div>
  );
}
