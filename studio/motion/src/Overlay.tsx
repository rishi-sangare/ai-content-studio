import React from 'react';
import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: LILITA } = loadLilita();

export type Word = { text: string; start: number; end: number; hl?: boolean };
export type Title = { text: string; start: number; end: number; kind?: 'hook' | 'stamp' | 'label' | 'sparkles'; y?: number; sub?: string; size?: number };
export type OverlayProps = {
  fps: number;
  duration: number;
  words: Word[];
  titles?: Title[];
  style?: { y?: number; accent?: string; accent2?: string; size?: number; maxWords?: number };
};

// ---------- captions: phrase groups that spring in; the spoken word lights up ----------
type Group = { words: Word[]; start: number; end: number };

function groupWords(words: Word[], maxWords: number): Group[] {
  const out: Group[] = [];
  let cur: Word[] = [];
  const flush = () => {
    if (cur.length) out.push({ words: cur, start: cur[0].start, end: cur[cur.length - 1].end });
    cur = [];
  };
  words.forEach((w, i) => {
    cur.push(w);
    const next = words[i + 1];
    const punct = /[.!?,…]$/.test(w.text);
    const gap = next ? next.start - w.end : 1;
    if (cur.length >= maxWords || punct || gap > 0.3) flush();
  });
  flush();
  // each group stays until the next one starts (no flicker), at most 0.6 s after its last word
  return out.map((g, i) => ({ ...g, end: Math.min(out[i + 1] ? out[i + 1].start : g.end + 0.6, g.end + 0.6) }));
}

const clean = (t: string) => t.replace(/^[\s"'“”]+|[\s,."'“”]+$/g, '').toUpperCase();

const CaptionGroup: React.FC<{ g: Group; idx: number; accent: string; accent2: string; size: number }> = ({ g, idx, accent, accent2, size }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps + g.start;                       // absolute time inside the Short
  const pop = spring({ frame, fps, config: { damping: 11, stiffness: 220, mass: 0.6 } });
  const scale = interpolate(pop, [0, 1], [0.55, 1]);
  const tilt = (idx % 2 ? 1 : -1) * 2.2 * (1 - pop);
  const long = g.words.reduce((a, w) => a + clean(w.text).length, 0) > 14;
  const fs = long ? size * 0.82 : size;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 30px', maxWidth: 940,
                  transform: `scale(${scale}) rotate(${tilt}deg)`, transformOrigin: '50% 50%' }}>
      {g.words.map((w, i) => {
        const active = t >= w.start - 0.02 && (i === g.words.length - 1 ? true : t < g.words[i + 1].start);
        const said = t >= w.start - 0.02;
        const k = spring({ frame: frame - Math.round((w.start - g.start) * fps), fps, config: { damping: 12, stiffness: 260 } });
        const color = w.hl ? (active ? accent2 : accent) : active ? '#FFFFFF' : said ? '#F4F4F4' : 'rgba(255,255,255,0.92)';
        return (
          <span key={i} style={{
            fontFamily: LILITA, fontSize: fs, lineHeight: 1.05, color, letterSpacing: 1,
            WebkitTextStroke: `${Math.round(fs * 0.11)}px #101010`, paintOrder: 'stroke fill',
            textShadow: '0 8px 0 rgba(0,0,0,0.55), 0 0 26px rgba(0,0,0,0.35)',
            transform: `scale(${active ? interpolate(k, [0, 1], [1.0, 1.07]) : 1}) translateY(${active ? -4 : 0}px)`,
            display: 'inline-block',
          }}>{clean(w.text)}</span>
        );
      })}
    </div>
  );
};

// ---------- magic dust: soft golden motes drifting up and twinkling (deterministic) ----------
const Sparkles: React.FC<{ seconds: number; count?: number }> = ({ seconds, count = 46 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const len = seconds * fps;
  const fade = Math.min(1, frame / (0.6 * fps), (len - frame) / (0.6 * fps));
  const rnd = (i: number, k: number) => { const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); };
  return (
    <AbsoluteFill style={{ opacity: Math.max(0, fade) }}>
      {Array.from({ length: count }).map((_, i) => {
        const x0 = rnd(i, 1) * 1080, y0 = 300 + rnd(i, 2) * 1500, sp = 40 + rnd(i, 3) * 90, size = 5 + rnd(i, 4) * 13;
        const t = frame / fps + rnd(i, 5) * 3;
        const y = y0 - sp * t, x = x0 + Math.sin(t * (0.6 + rnd(i, 6))) * 26;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(t * (1.5 + rnd(i, 7) * 2.5)));
        return <div key={i} style={{ position: 'absolute', left: x, top: y, width: size, height: size, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,250,215,1) 0%, rgba(255,214,90,0.85) 40%, rgba(255,200,60,0) 72%)',
          opacity: tw, filter: 'blur(0.4px)', boxShadow: `0 0 ${size * 2.2}px rgba(255,214,90,0.55)` }} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- titles: hook banner, date stamp, small label ----------
const TitleCard: React.FC<{ title: Title; accent: string }> = ({ title, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const len = (title.end - title.start) * fps;
  const inn = spring({ frame, fps, config: { damping: 10, stiffness: 180 } });
  const out = interpolate(frame, [len - 6, len], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const kind = title.kind || 'hook';
  if (kind === 'sparkles') return <Sparkles seconds={title.end - title.start} />;
  if (kind === 'stamp') {
    const s = interpolate(inn, [0, 1], [2.4, 1]);
    return (
      <div style={{ transform: `scale(${s}) rotate(-6deg)`, opacity: Math.min(1, inn * 1.4) * out, padding: '14px 34px',
                    border: `8px solid ${accent}`, borderRadius: 22, background: 'rgba(16,16,16,0.72)' }}>
        <div style={{ fontFamily: LILITA, fontSize: 92, color: accent, letterSpacing: 2, lineHeight: 1 }}>{title.text}</div>
        {title.sub ? <div style={{ fontFamily: LILITA, fontSize: 44, color: '#fff', textAlign: 'center', marginTop: 6 }}>{title.sub}</div> : null}
      </div>
    );
  }
  if (kind === 'label') {
    const x = interpolate(inn, [0, 1], [-60, 0]);
    return (
      <div style={{ transform: `translateX(${x}px)`, opacity: inn * out, padding: '10px 22px', borderRadius: 16,
                    background: accent, fontFamily: LILITA, fontSize: 66, color: '#151515', boxShadow: '0 6px 0 rgba(0,0,0,0.45)' }}>{title.text}</div>
    );
  }
  const y = interpolate(inn, [0, 1], [-40, 0]);
  return (
    <div style={{ transform: `translateY(${y}px)`, opacity: Math.min(1, inn * 1.3) * out, maxWidth: 960, textAlign: 'center',
                  fontFamily: LILITA, fontSize: title.size ?? 78, lineHeight: 1.08, color: '#fff', padding: '16px 30px', borderRadius: 26,
                  background: 'rgba(12,12,12,0.70)', WebkitTextStroke: '0px', textShadow: '0 5px 0 rgba(0,0,0,0.5)' }}>
      {title.text}
      {title.sub ? <div style={{ fontSize: 46, color: accent, marginTop: 6 }}>{title.sub}</div> : null}
    </div>
  );
};

export const Overlay: React.FC<OverlayProps> = ({ fps, words, titles = [], style = {} }) => {
  const groups = groupWords(words, style.maxWords ?? 3);
  const accent = style.accent ?? '#FFD23F';
  const accent2 = style.accent2 ?? '#7CFF6B';
  const size = style.size ?? 104;
  const yCap = style.y ?? 0.66;
  return (
    <AbsoluteFill style={{ backgroundColor: 'transparent' }}>
      {titles.map((tt, i) => (
        <Sequence key={`t${i}`} from={Math.round(tt.start * fps)} durationInFrames={Math.max(1, Math.round((tt.end - tt.start) * fps))}>
          {tt.kind === 'sparkles' ? <TitleCard title={tt} accent={accent} /> : (
          <AbsoluteFill style={{ alignItems: 'center', top: `${(tt.y ?? 0.16) * 100}%`, height: 'auto' }}>
            <TitleCard title={tt} accent={accent} />
          </AbsoluteFill>)}
        </Sequence>
      ))}
      {groups.map((g, i) => (
        <Sequence key={`g${i}`} from={Math.round(g.start * fps)} durationInFrames={Math.max(1, Math.round((g.end - g.start) * fps))}>
          <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', top: `${(yCap - 0.5) * 100}%` }}>
            <CaptionGroup g={g} idx={i} accent={accent} accent2={accent2} size={size} />
          </AbsoluteFill>
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
