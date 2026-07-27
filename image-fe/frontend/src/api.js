async function j(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${path} failed (${r.status}): ${text}`);
  }
  return r.json();
}

function post(path, body) {
  return j(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function put(path, body) {
  return j(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function del(path) {
  return j(path, { method: "DELETE" });
}

export const getDefaults = () => j("/api/defaults");
export const getOptions = () => j("/api/options");
export const getHistory = (limit, beforeId) =>
  j(`/api/history?limit=${limit}${beforeId ? `&before_id=${beforeId}` : ""}`);
export const deleteGeneration = (id) => del(`/api/history/${id}`);

export function generateImage(params) {
  return j("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/**
 * Subscribes to the SSE progress stream for a prompt_id.
 * Resolves once the stream reaches a terminal state (done/error/connection loss).
 */
export function streamGeneration(promptId, { onProgress, onDone, onError }) {
  return new Promise((resolve) => {
    const es = new EventSource(`/api/stream/${promptId}`);

    es.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "progress") {
        onProgress({ value: msg.value, max: msg.max });
      } else if (msg.type === "done") {
        onDone(msg);
        es.close();
        resolve();
      } else if (msg.type === "error") {
        onError(msg.message);
        es.close();
        resolve();
      }
    };

    es.onerror = () => {
      onError("Connection to server lost");
      es.close();
      resolve();
    };
  });
}

// ---------------------------------------------------------------- chat

export const getChatDefaults = () => j("/api/chat/defaults");
export const getChatModels = () => j("/api/chat/models");

export const getCharacters = () => j("/api/characters");
export const createCharacter = (char) => post("/api/characters", char);
export const updateCharacter = (id, char) => put(`/api/characters/${id}`, char);
export const deleteCharacter = (id) => del(`/api/characters/${id}`);
export async function uploadCharacterAvatar(id, file) {
  const fd = new FormData();
  fd.append("file", file);
  return j(`/api/characters/${id}/avatar`, { method: "POST", body: fd });
}
export const importCharacter = (card) => post("/api/characters/import", card);

export const getConversations = (characterId) =>
  j(`/api/conversations${characterId ? `?character_id=${characterId}` : ""}`);
export const createConversation = (characterId, title = "", presetId = null) =>
  post("/api/conversations", { character_id: characterId, title, preset_id: presetId });
export const getConversation = (id) => j(`/api/conversations/${id}`);
export const deleteConversation = (id) => del(`/api/conversations/${id}`);
export const updateMessage = (id, content) => put(`/api/messages/${id}`, { content });
export const deleteMessage = (id) => del(`/api/messages/${id}`);

export const getPresets = () => j("/api/presets");
export const createPreset = (preset) => post("/api/presets", preset);
export const updatePreset = (id, preset) => put(`/api/presets/${id}`, preset);
export const deletePreset = (id) => del(`/api/presets/${id}`);

export const sendChatMessage = (params) => post("/api/chat/send", params);
export const impersonate = (params) => post("/api/chat/impersonate", params);
export const summarizeConversation = (params) => post("/api/chat/summarize", params);
export const saveSummary = (convId, params) => post(`/api/conversations/${convId}/summary`, params);

/**
 * Subscribes to the SSE token stream for a chat stream_id.
 * Resolves once the stream reaches a terminal state (done/error/connection loss).
 */
export function streamChat(streamId, { onToken, onDone, onError }) {
  return new Promise((resolve) => {
    const es = new EventSource(`/api/chat/stream/${streamId}`);

    es.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.type === "token") {
        onToken(msg.content);
      } else if (msg.type === "done") {
        onDone(msg);
        es.close();
        resolve();
      } else if (msg.type === "error") {
        onError(msg.message);
        es.close();
        resolve();
      }
    };

    es.onerror = () => {
      onError("Connection to server lost");
      es.close();
      resolve();
    };
  });
}
