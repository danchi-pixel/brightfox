import { useEffect, useRef, useState } from "react";
import type { Picture, Source } from "./types";

/** SVG viewport crops the original private photograph without editing its scientific detail. */
export function SourcePicture({ picture, sources, base }: { picture: Picture; sources: Source[]; base: string }) {
  const [failed, setFailed] = useState(false);
  const [full, setFull] = useState(false);
  const figure = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(typeof IntersectionObserver === "undefined");
  useEffect(() => {
    if (visible || !figure.current) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, { rootMargin: "200px" });
    observer.observe(figure.current);
    return () => observer.disconnect();
  }, [visible]);
  const source = sources.find(s => s.id === picture.source);
  if (!source) return <p role="alert">Vir slike ni na voljo.</p>;
  const w = source.rotate ? source.height : source.width;
  const h = source.rotate ? source.width : source.height;
  const box = full ? [0, 0, w, h] : picture.box;
  return <figure className="science-picture" ref={figure}>
    {failed ? <p role="alert">Slike ni mogoče naložiti. Povej staršem, naj preverijo prenos gradiva. <button onClick={() => { setFailed(false); }}>Poskusi znova</button></p> :
      <svg role="img" aria-label={picture.alt} viewBox={box.join(" ")} style={{ aspectRatio: `${box[2]} / ${box[3]}` }}>
        {visible && <image href={`${base}/images/${source.id}`} width={source.width} height={source.height}
          transform={source.rotate === 90 ? `translate(${source.height} 0) rotate(90)` : source.rotate === -90 ? `translate(0 ${source.width}) rotate(-90)` : undefined} onError={() => setFailed(true)} />}
      </svg>}
    <figcaption><span>{source.label}</span><button type="button" onClick={() => setFull(!full)}>{full ? "Pokaži izrez" : "Povečaj / cela stran"}</button></figcaption>
  </figure>;
}
