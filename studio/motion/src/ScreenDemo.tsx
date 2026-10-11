import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, interpolate, Easing } from 'remotion';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: INTER } = loadInter('normal', { weights: ['500', '600'], subsets: ['latin'] });
const { fontFamily: LILITA } = loadLilita();

// "Screen demo" panel: a real page screenshot inside a browser frame, driven like a screen recording —
// typed URL, page load, smooth scroll, camera zoom onto what matters, a cursor that moves / clicks, marker boxes,
// result cards. All positions are in the screenshot's own pixels (1080 wide, 2x), so a timeline is easy to write.
// The same timeline JSON drives the sounds (typing, clicks) in studio/render — see streams/ainews/demo.py.

type Key = { t: number; x: number; y: number; s?: number };
export type DemoScene = { start: number; end: number; img: string; imgH: number; url: string; typeFrom?: number; typeTo?: number; loadAt?: number };
export type DemoProps = {
  fps: number;
  duration: number;
  width?: number;
  height?: number;
  scenes: DemoScene[];
  cam: Key[];
  cursor: Key[];
  clicks: number[];
  marks?: { start: number; end: number; x0: number; y0: number; x1: number; y1: number; color?: string }[];
  cards?: { start: number; end: number; text: string; sub?: string; tag?: string; color?: string }[];
};

const ease = Easing.bezier(0.65, 0, 0.35, 1);

function at(keys: Key[], t: number): Required<Key> {
  const k = keys.filter((q) => q.t <= t).length - 1;
  const a = keys[Math.max(0, k)], b = keys[Math.min(keys.length - 1, k + 1)];
  const full = (q: Key) => ({ t: q.t, x: q.x, y: q.y, s: q.s ?? 1 });
  if (k < 0) return full(keys[0]);
  if (k >= keys.length - 1 || b.t === a.t) return full(a);
  // a keyframe is where the value ARRIVES; it starts moving after the previous one, eased
  const p = ease(Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t))));
  const A = full(a), B = full(b);
  return { t, x: A.x + (B.x - A.x) * p, y: A.y + (B.y - A.y) * p, s: A.s + (B.s - A.s) * p };
}

export const ScreenDemo: React.FC<DemoProps> = (p) => {
  const frame = useCurrentFrame();
  const t = frame / p.fps;
  const W = p.width ?? 1080, H = p.height ?? 900;
  const M = 28, BAR = 66;                                   // frame margin, browser bar height
  const vw = W - 2 * M, vh = H - 2 * M - BAR;               // page viewport
  const base = vw / 1080;
  const scene = p.scenes.find((s) => t >= s.start && t < s.end) ?? p.scenes[p.scenes.length - 1];
  const st = t - scene.start;
  const loaded = scene.loadAt === undefined || t >= scene.loadAt;
  const cam = at(p.cam, t);
  const sc = base * cam.s;
  // image point (cam.x, cam.y) sits at the viewport centre
  const tx = vw / 2 - cam.x * sc, ty = vh / 2 - cam.y * sc;
  const toScreen = (x: number, y: number) => [M + tx + x * sc, M + BAR + ty + y * sc];

  // typed URL
  let url = scene.url;
  if (scene.typeFrom !== undefined && scene.typeTo !== undefined) {
    const n = Math.round(interpolate(t, [scene.typeFrom, scene.typeTo], [0, scene.url.length], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
    url = scene.url.slice(0, n);
  }
  const caret = !loaded && Math.floor(t * 2.5) % 2 === 0;
  const loadP = scene.loadAt === undefined ? 1 : interpolate(t, [scene.loadAt, scene.loadAt + 0.35], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pageIn = scene.loadAt === undefined ? 1 : interpolate(t, [scene.loadAt + 0.05, scene.loadAt + 0.25], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // cursor + clicks
  const cur = at(p.cursor, t);
  const [cx, cy] = toScreen(cur.x, cur.y);
  const lastClick = p.clicks.filter((c) => c <= t).pop();
  const since = lastClick === undefined ? 99 : t - lastClick;
  const press = since < 0.12 ? 0.82 : since < 0.22 ? interpolate(since, [0.12, 0.22], [0.82, 1]) : 1;

  return (
    <AbsoluteFill style={{ background: 'transparent' }}>
      <div style={{ position: 'absolute', left: M, top: M, width: vw, height: vh + BAR, borderRadius: 26, overflow: 'hidden',
        background: '#fff', boxShadow: '0 18px 50px rgba(0,0,0,0.55)', border: '3px solid rgba(255,255,255,0.9)' }}>
        {/* browser bar */}
        <div style={{ height: BAR, background: '#ECECF1', display: 'flex', alignItems: 'center', padding: '0 20px', gap: 12 }}>
          {['#FF5F57', '#FEBC2E', '#28C840'].map((c) => <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />)}
          <div style={{ flex: 1, marginLeft: 14, height: 42, borderRadius: 21, background: '#fff', display: 'flex', alignItems: 'center',
            padding: '0 20px', fontFamily: INTER, fontSize: 26, color: '#222', fontWeight: 500 }}>
            <span style={{ color: '#888', marginRight: 10 }}>🔒</span>{url}{caret ? <span style={{ color: '#3b82f6' }}>|</span> : null}
          </div>
        </div>
        {/* loading bar */}
        {loadP > 0 && loadP < 1 ? <div style={{ position: 'absolute', top: BAR - 4, left: 0, height: 4, width: `${loadP * 100}%`, background: '#3b82f6' }} /> : null}
        {/* page */}
        <div style={{ position: 'absolute', top: BAR, left: 0, width: vw, height: vh, overflow: 'hidden', background: '#fff' }}>
          {loaded ? (
            <div style={{ position: 'absolute', left: 0, top: 0, transformOrigin: '0 0', opacity: pageIn,
              transform: `translate(${tx}px, ${ty}px) scale(${sc})` }}>
              <Img src={staticFile(scene.img)} style={{ width: 1080, height: scene.imgH, display: 'block' }} />
              {(p.marks ?? []).filter((m) => t >= m.start && t < m.end).map((m, i) => {
                const g = interpolate(t, [m.start, m.start + 0.3], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2)) });
                return <div key={i} style={{ position: 'absolute', left: m.x0 - 12, top: m.y0 - 10, width: m.x1 - m.x0 + 24, height: m.y1 - m.y0 + 20,
                  border: `${6 / cam.s}px solid ${m.color ?? '#FFD23F'}`, borderRadius: 14, transform: `scale(${g})`,
                  boxShadow: `0 0 ${24 / cam.s}px ${m.color ?? '#FFD23F'}`, background: 'rgba(255,210,63,0.12)' }} />;
              })}
            </div>
          ) : null}
        </div>
      </div>
      {/* cursor (screen space, follows the page point it hovers) */}
      {t > 0.05 ? (
        <svg width={56} height={56} viewBox="0 0 24 24" style={{ position: 'absolute', left: cx - 8, top: cy - 5, transform: `scale(${press})`, transformOrigin: '8px 5px',
          filter: 'drop-shadow(0 3px 4px rgba(0,0,0,0.45))' }}>
          <path d="M5 2 L5 20 L9.5 15.8 L12.6 22.4 L15.4 21.1 L12.4 14.7 L18.6 14.4 Z" fill="#fff" stroke="#111" strokeWidth="1.4" strokeLinejoin="round" />
        </svg>
      ) : null}
      {since < 0.45 ? (
        <div style={{ position: 'absolute', left: cx - 40, top: cy - 40, width: 80, height: 80, borderRadius: 40,
          border: '5px solid rgba(59,130,246,0.9)', transform: `scale(${interpolate(since, [0, 0.45], [0.3, 1.4])})`,
          opacity: interpolate(since, [0, 0.45], [1, 0]) }} />
      ) : null}
      {/* result cards */}
      {(p.cards ?? []).filter((c) => t >= c.start && t < c.end).map((c, i) => {
        const g = interpolate(t, [c.start, c.start + 0.28], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2.2)) });
        return (
          <div key={i} style={{ position: 'absolute', left: W / 2 - 400, top: H / 2 - 120, width: 800, padding: '26px 30px', borderRadius: 28,
            background: '#111', border: `5px solid ${c.color ?? '#FF4D4D'}`, boxShadow: '0 20px 60px rgba(0,0,0,0.6)', transform: `scale(${g})`,
            textAlign: 'center' }}>
            {c.tag ? <div style={{ fontFamily: INTER, fontSize: 24, color: '#aaa', letterSpacing: 2, marginBottom: 6 }}>{c.tag}</div> : null}
            <div style={{ fontFamily: LILITA, fontSize: 82, color: c.color ?? '#FF4D4D', lineHeight: 1 }}>{c.text}</div>
            {c.sub ? <div style={{ fontFamily: INTER, fontSize: 34, color: '#fff', marginTop: 10, fontWeight: 600 }}>{c.sub}</div> : null}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
