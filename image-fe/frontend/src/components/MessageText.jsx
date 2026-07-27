const PATTERN = /(\*[^*]+\*|"[^"]+")/g;

export default function MessageText({ text }) {
  return text.split(PATTERN).map((part, i) => {
    if (part.startsWith("*") && part.endsWith("*") && part.length > 1) {
      return (
        <em key={i} className="msg-action">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith('"') && part.endsWith('"') && part.length > 1) {
      return (
        <span key={i} className="msg-dialogue">
          {part}
        </span>
      );
    }
    return part;
  });
}
