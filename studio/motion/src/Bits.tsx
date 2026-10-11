import React from 'react';
import { Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, interpolate, Easing } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

// Shared pieces for the AI-news reel formats (StreamReel / CardsReel / ChatReel): word-by-word captions coloured by speaker,
// reaction GIF pop-ups, emoji pops, the deprecation HUD, full-body characters. All timings are seconds.

export const { fontFamily: LILITA } = loadLilita();

export type Who = string;
export type CastMember = { id: Who; side: 'left' | 'right'; color: string; height: number };
export type Word = { text: string; start: number; end: number; who: Who };
export type Line = { start: number; end: number; who: Who; faces: Record<string, string> };
export type Gif = { t: number; dur: number; src: string; x: number; y: number; w: number; h: number; rot?: number };
export type Emoji = { t: number; e: string; x: number; y: number; size?: number };
export type Hud = { start: number; end: number; text: string; color?: string; flash?: boolean };

export const useT = (fps: number) => useCurrentFrame() / fps;

export function currentLine(lines: Line[], t: number) {
  return [...lines].reverse().find((l) => t >= l.start - 0.05) ?? lines[0];
}

function chunks(words: Word[]) {
  const out: { words: Word[]; start: number; end: number }[] = [];
  let cur: Word[] = [];
  words.forEach((w, i) => {
    cur.push(w);
    const next = words[i + 1];
    const brk = !next || next.who !== w.who || cur.length >= 3 || /[.,?!…:]$/.test(w.text) || next.start - w.end > 0.35;
    if (brk) {
      out.push({ words: cur, start: cur[0].start, end: next ? Math.min(next.start, w.end + 0.5) : w.end + 0.6 });
      cur = [];
    }
  });
  return out;
}

export const Captions: React.FC<{ words: Word[]; t: number; y: number; color: (w: Who) => string; size?: number }> = ({ words, t, y, color, size = 100 }) => {
  const ch = chunks(words).find((c) => t >= c.start && t < c.end);
  if (!ch) return null;
  return (
    <div style={{ position: 'absolute', top: y, left: 50, width: 980, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 22px',
      transform: `scale(${interpolate(t, [ch.start, ch.start + 0.1], [0.85, 1], { extrapolateRight: 'clamp' })})` }}>
      {ch.words.map((w, i) => (
        <span key={i} style={{ fontFamily: LILITA, fontSize: size, lineHeight: 1.08, letterSpacing: 1,
          color: t >= w.start - 0.03 ? color(w.who) : '#ffffff', WebkitTextStroke: '10px #000', paintOrder: 'stroke fill',
          textShadow: '0 6px 12px rgba(0,0,0,0.5)' }}>{w.text}</span>
      ))}
    </div>
  );
};

export const GifPops: React.FC<{ gifs: Gif[]; fps: number; t: number }> = ({ gifs, fps, t }) => (
  <>
    {gifs.map((g, i) => {
      const s = t - g.t;
      const sc = interpolate(s, [0, 0.12, 0.2], [0.3, 1.1, 1], { extrapolateRight: 'clamp' });
      const out = interpolate(s, [g.dur - 0.12, g.dur], [1, 0.2], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
      return (
        <Sequence key={i} from={Math.round(g.t * fps)} durationInFrames={Math.round(g.dur * fps)} layout="none">
          <div style={{ position: 'absolute', left: g.x, top: g.y, width: g.w, height: g.h, borderRadius: 22, overflow: 'hidden',
            border: '7px solid #fff', boxShadow: '0 16px 40px rgba(0,0,0,0.6)', transform: `rotate(${g.rot ?? 0}deg) scale(${sc * out})` }}>
            <OffthreadVideo src={staticFile(g.src)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
        </Sequence>
      );
    })}
  </>
);

export const EmojiPops: React.FC<{ emojis: Emoji[]; t: number }> = ({ emojis, t }) => (
  <>
    {emojis.filter((e) => t >= e.t && t < e.t + 1.3).map((e, i) => {
      const s = t - e.t;
      const sc = interpolate(s, [0, 0.18, 0.3], [0.2, 1.25, 1], { extrapolateRight: 'clamp' });
      const op = interpolate(s, [1.0, 1.3], [1, 0], { extrapolateLeft: 'clamp' });
      return <div key={i} style={{ position: 'absolute', left: e.x, top: e.y - s * 40, fontSize: e.size ?? 150,
        transform: `scale(${sc}) rotate(${Math.sin(s * 9) * 8}deg)`, opacity: op }}>{e.e}</div>;
    })}
  </>
);

export const HudBar: React.FC<{ hud: Hud[]; t: number; x: number; y: number }> = ({ hud, t, x, y }) => (
  <>
    {hud.filter((h) => t >= h.start && t < h.end).map((h, i) => {
      const s = t - h.start;
      const sc = interpolate(s, [0, 0.12, 0.22], [0.7, 1.12, 1], { extrapolateRight: 'clamp' });
      const on = !h.flash || Math.floor(s * 6) % 2 === 0 || s > 1.2;
      return (
        <div key={i} style={{ position: 'absolute', top: y, left: x, padding: '8px 20px', borderRadius: 14,
          background: 'rgba(15,15,20,0.88)', border: `3px solid ${h.color ?? '#FF4D4D'}`, transform: `scale(${sc})`, transformOrigin: 'left center',
          fontFamily: LILITA, fontSize: 38, letterSpacing: 1, color: on ? (h.color ?? '#FF5A5A') : '#fff' }}>⚠️ {h.text}</div>
      );
    })}
  </>
);

export const Body: React.FC<{ c: CastMember; face: string; speaking: boolean; amp: number; since: number; bottom?: number }> = ({ c, face, speaking, amp, since, bottom = -6 }) => {
  const pop = interpolate(since, [0, 0.14], [0.93, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(3)) });
  const base = speaking ? 1 : 0.9;
  return (
    <Img src={staticFile(`chars/${c.id}_${face}.png`)} style={{
      position: 'absolute', bottom, [c.side]: 6, height: c.height, transformOrigin: 'bottom center',
      transform: `translateY(${speaking ? -amp * 22 : 0}px) scale(${base * pop}, ${base * pop * (1 + (speaking ? amp * 0.035 : 0))})`,
      filter: `drop-shadow(0 10px 18px rgba(0,0,0,0.5)) brightness(${speaking ? 1 : 0.62})`,
    }} />
  );
};

export const Chip: React.FC<{ text: string; t: number; start?: number; bg?: string; size?: number; rot?: number }> = ({ text, t, start = 0, bg = '#E8344E', size = 60, rot = -2 }) => (
  <div style={{ fontFamily: LILITA, fontSize: size, color: '#fff', background: bg, padding: '8px 26px', borderRadius: 18,
    transform: `scale(${interpolate(t - start, [0, 0.25], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2.5)) })}) rotate(${rot}deg)`,
    boxShadow: '0 8px 24px rgba(0,0,0,0.45)', display: 'inline-block' }}>{text}</div>
);
