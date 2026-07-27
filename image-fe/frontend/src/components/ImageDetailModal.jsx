export default function ImageDetailModal({ item, onClose, onReuse, onDelete }) {
  if (!item) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>
          ✕
        </button>

        <div className="modal-images">
          {item.images.map((src) => (
            <img key={src} src={src} alt={item.prompt} />
          ))}
        </div>

        <div className="modal-details">
          <label>Prompt</label>
          <p>{item.prompt || <em>(empty)</em>}</p>

          <label>Negative prompt</label>
          <p>{item.negative_prompt || <em>(empty)</em>}</p>

          <div className="modal-grid">
            <div>
              <label>Model</label>
              <p>{item.model}</p>
            </div>
            <div>
              <label>Size</label>
              <p>
                {item.width} × {item.height}
              </p>
            </div>
            <div>
              <label>Steps</label>
              <p>{item.steps}</p>
            </div>
            <div>
              <label>CFG</label>
              <p>{item.cfg}</p>
            </div>
            <div>
              <label>Sampler</label>
              <p>{item.sampler_name}</p>
            </div>
            <div>
              <label>Scheduler</label>
              <p>{item.scheduler}</p>
            </div>
            <div>
              <label>Denoise</label>
              <p>{item.denoise}</p>
            </div>
            <div>
              <label>Batch size</label>
              <p>{item.batch_size}</p>
            </div>
            <div>
              <label>Seed</label>
              <p>{item.seed}</p>
            </div>
            <div>
              <label>LoRAs</label>
              <p>
                {item.loras && item.loras.length
                  ? item.loras.map((l) => `${l.name} (${l.strength})`).join(", ")
                  : "none"}
              </p>
            </div>
          </div>

          {item.created_at && (
            <p className="modal-date">{new Date(item.created_at).toLocaleString()}</p>
          )}
        </div>

        <div className="modal-buttons">
          <button type="button" onClick={() => onReuse(item)}>
            Use these settings
          </button>
          <button type="button" className="danger" onClick={() => onDelete(item)}>
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
