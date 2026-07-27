import { useCallback, useEffect, useRef, useState } from "react";
import PromptForm from "../components/PromptForm";
import ProgressBar from "../components/ProgressBar";
import Gallery from "../components/Gallery";
import ImageDetailModal from "../components/ImageDetailModal";
import {
  deleteGeneration,
  generateImage,
  getDefaults,
  getHistory,
  getOptions,
  streamGeneration,
} from "../api";

const PAGE_SIZE = 60;

export default function ImagesPage() {
  const [form, setForm] = useState(null);
  const [options, setOptions] = useState({ checkpoints: [], samplers: [], schedulers: [], loras: [] });
  const [history, setHistory] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState(null);
  const historyRef = useRef(history);
  const loadingMoreRef = useRef(false);
  const sentinelRef = useRef(null);

  useEffect(() => {
    historyRef.current = history;
  }, [history]);

  useEffect(() => {
    (async () => {
      try {
        const [defaults, opts, hist] = await Promise.all([
          getDefaults(),
          getOptions(),
          getHistory(PAGE_SIZE),
        ]);
        setForm(defaults);
        setOptions(opts);
        setHistory(hist);
        setHasMore(hist.length === PAGE_SIZE);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current) return;
    const last = historyRef.current[historyRef.current.length - 1];
    if (!last) return;
    loadingMoreRef.current = true;
    try {
      const older = await getHistory(PAGE_SIZE, last.id);
      setHistory((h) => {
        const seen = new Set(h.map((x) => x.id));
        return [...h, ...older.filter((x) => !seen.has(x.id))];
      });
      setHasMore(older.length === PAGE_SIZE);
    } catch (e) {
      setError(String(e));
    } finally {
      loadingMoreRef.current = false;
    }
  }, []);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { rootMargin: "600px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore, hasMore]);

  const handleGenerate = useCallback(async (params) => {
    setError(null);
    setBusy(true);
    setProgress({ value: 0, max: params.steps });
    try {
      const { prompt_id, seed } = await generateImage(params);
      setForm((f) => ({ ...f, seed }));
      await streamGeneration(prompt_id, {
        onProgress: setProgress,
        onDone: (result) => {
          setHistory((h) => [
            { id: result.generation_id, images: result.images, ...params, seed },
            ...h,
          ]);
          setProgress(null);
          setBusy(false);
        },
        onError: (msg) => {
          setError(msg);
          setProgress(null);
          setBusy(false);
        },
      });
    } catch (e) {
      setError(String(e));
      setProgress(null);
      setBusy(false);
    }
  }, []);

  const handleReuse = useCallback((item) => {
    setForm((f) => ({
      ...f,
      prompt: item.prompt,
      negative_prompt: item.negative_prompt,
      width: item.width,
      height: item.height,
      steps: item.steps,
      cfg: item.cfg,
      sampler_name: item.sampler_name,
      scheduler: item.scheduler,
      denoise: item.denoise,
      batch_size: item.batch_size,
      seed: item.seed,
      model: item.model,
      loras: item.loras || [],
      randomize_seed: false,
    }));
    setViewing(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleDelete = useCallback(async (item) => {
    if (!window.confirm("Delete this generation? This cannot be undone.")) return;
    try {
      await deleteGeneration(item.id);
      setHistory((h) => h.filter((x) => x.id !== item.id));
      setViewing(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  if (!form) {
    return <div className="loading">Loading…</div>;
  }

  return (
    <>
      <PromptForm form={form} setForm={setForm} options={options} onGenerate={handleGenerate} busy={busy} />
      {progress && <ProgressBar value={progress.value} max={progress.max} />}
      {error && <div className="error">{error}</div>}
      <Gallery items={history} onView={setViewing} />
      {hasMore && <div ref={sentinelRef} className="gallery-sentinel" aria-hidden="true" />}
      <ImageDetailModal
        item={viewing}
        onClose={() => setViewing(null)}
        onReuse={handleReuse}
        onDelete={handleDelete}
      />
    </>
  );
}
