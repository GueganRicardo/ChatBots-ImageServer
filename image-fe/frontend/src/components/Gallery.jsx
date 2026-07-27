export default function Gallery({ items, onView }) {
  if (!items.length) {
    return <p className="empty">No images yet — generate your first one above.</p>;
  }

  return (
    <div className="gallery">
      {items.map((item) => (
        <div className="gallery-item" key={item.id}>
          {item.images.map((src) => (
            <img
              key={src}
              src={src}
              loading="lazy"
              alt={item.prompt}
              onClick={() => onView(item)}
            />
          ))}
          <p className="gallery-caption" title={item.prompt}>
            {item.prompt}
          </p>
        </div>
      ))}
    </div>
  );
}
