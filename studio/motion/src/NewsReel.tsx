import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, interpolate, Easing } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';
import { ScreenDemo, DemoProps } from './ScreenDemo';
import { Parkour } from './Parkour';

const { fontFamily: LILITA } = loadLilita();

// AI-news reel (streams/ainews): top = ScreenDemo (the real site being used), bottom = our voxel parkour run with the two
// characters in the corners (speaker bounces to the voice, listener dims), word-by-word captions coloured by speaker,
// reaction GIF pop-ups, emojis, a running-gag HUD bar. Audio is mixed outside (studio/render). Props come from the reel's build.py.

type Who = string;
export type CastMember = { id: Who; side: 'left' | 'right'; color: string; height: number };
export type ReelProps = {
  fps: number;
  duration: number;
  demo: DemoProps;
  cast?: CastMember[];
  words: { text: string; start: number; end: number; who: Who }[];
  lines: { start: number; end: number; who: Who; faces?: Record<string, string>; [k: string]: unknown }[];
  amp: number[];                                   // voice loudness per frame, 0..1
  emojis?: { t: number; e: string; who: Who }[];
  gifs?: { t: number; dur: number; src: string; x: number; y: number; w: number; h: number; rot?: number }[];
  hud?: { start: number; end: number; text: string; color?: string; flash?: boolean }[];
  hook?: { text: string; end: number };
  seed?: number;
};

const TOP = 900;
const DEFAULT_CAST: CastMember[] = [
  { id: 'miko', side: 'left', color: '#FF6FB5', height: 640 },
  { id: 'ren', side: 'right', color: '#3FE0D0', height: 640 },
];

function chunks(words: ReelProps['words']) {
  const out: { words: ReelProps['words']; start: number; end: number }[] = [];
  let cur: ReelProps['words'] = [];
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

const Character: React.FC<{ c: CastMember; face: string; speaking: boolean; amp: number; since: number }> = ({ c, face, speaking, amp, since }) => {
  const pop = interpolate(since, [0, 0.14], [0.93, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(3)) });
  const base = speaking ? 1 : 0.9;
  const lift = speaking ? amp * 22 : 0;
  return (
    <Img src={staticFile(`chars/${c.id}_${face}.png`)} style={{
      position: 'absolute', bottom: -6, [c.side]: 6, height: c.height,
      transformOrigin: 'bottom center',
      transform: `translateY(${-lift}px) scale(${base * pop}, ${base * pop * (1 + (speaking ? amp * 0.035 : 0))})`,
      filter: `drop-shadow(0 10px 18px rgba(0,0,0,0.5)) brightness(${speaking ? 1 : 0.62})`,
    }} />
  );
};

export const NewsReel: React.FC<ReelProps> = (p) => {
  const frame = useCurrentFrame();
  const t = frame / p.fps;
  const cast = p.cast ?? DEFAULT_CAST;
  const color = (w: Who) => cast.find((c) => c.id === w)?.color ?? '#FFD23F';
  const side = (w: Who) => cast.find((c) => c.id === w)?.side ?? 'left';
  const amp = p.amp[Math.min(frame, p.amp.length - 1)] ?? 0;
  const line = [...p.lines].reverse().find((l) => t >= l.start - 0.05) ?? p.lines[0];
  const speaking = t <= line.end + 0.05 ? line.who : null;
  const cs = chunks(p.words);
  const ch = cs.find((c) => t >= c.start && t < c.end);
  const faceOf = (id: Who) => (line.faces?.[id] ?? (line[id] as string) ?? 'neutral');

  return (
    <AbsoluteFill style={{ background: 'linear-gradient(180deg, #17121f 0%, #0d1a24 100%)' }}>
      {/* bottom: parkour */}
      <div style={{ position: 'absolute', top: TOP, left: 0, width: 1080, height: 1920 - TOP, overflow: 'hidden' }}>
        <Parkour width={1080} height={1920 - TOP} seed={p.seed ?? 7} duration={p.duration} />
      </div>
      <div style={{ position: 'absolute', top: TOP - 3, left: 0, width: 1080, height: 6, background: `linear-gradient(90deg,${cast[0].color},${cast[1].color})` }} />
      {/* top: the real site, being used */}
      <div style={{ position: 'absolute', top: 0, left: 0, width: 1080, height: TOP }}>
        <ScreenDemo {...p.demo} width={1080} height={TOP} />
      </div>
      {/* running-gag HUD */}
      {(p.hud ?? []).filter((h) => t >= h.start && t < h.end).map((h, i) => {
        const s = t - h.start;
        const sc = interpolate(s, [0, 0.12, 0.22], [0.7, 1.12, 1], { extrapolateRight: 'clamp' });
        const on = !h.flash || Math.floor(s * 6) % 2 === 0 || s > 1.2;
        return (
          <div key={i} style={{ position: 'absolute', top: TOP + 24, left: 24, padding: '8px 20px', borderRadius: 14,
            background: 'rgba(15,15,20,0.88)', border: `3px solid ${h.color ?? '#FF4D4D'}`, transform: `scale(${sc})`, transformOrigin: 'left center',
            fontFamily: LILITA, fontSize: 38, letterSpacing: 1, color: on ? (h.color ?? '#FF5A5A') : '#fff' }}>⚠️ {h.text}</div>
        );
      })}
      {/* characters */}
      {cast.map((c) => (
        <Character key={c.id} c={c} face={faceOf(c.id)} speaking={speaking === c.id} amp={speaking === c.id ? amp : 0} since={t - line.start} />
      ))}
      {/* reaction GIFs */}
      {(p.gifs ?? []).map((g, i) => {
        const from = Math.round(g.t * p.fps), dur = Math.round(g.dur * p.fps);
        const s = t - g.t;
        const sc = interpolate(s, [0, 0.12, 0.2], [0.3, 1.1, 1], { extrapolateRight: 'clamp' });
        const out = interpolate(s, [g.dur - 0.12, g.dur], [1, 0.2], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        return (
          <Sequence key={i} from={from} durationInFrames={dur} layout="none">
            <div style={{ position: 'absolute', left: g.x, top: g.y, width: g.w, height: g.h, borderRadius: 22, overflow: 'hidden',
              border: '7px solid #fff', boxShadow: '0 16px 40px rgba(0,0,0,0.6)', transform: `rotate(${g.rot ?? 0}deg) scale(${sc * out})` }}>
              <OffthreadVideo src={staticFile(g.src)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          </Sequence>
        );
      })}
      {/* emoji reactions */}
      {(p.emojis ?? []).filter((e) => t >= e.t && t < e.t + 1.3).map((e, i) => {
        const s = t - e.t;
        const sc = interpolate(s, [0, 0.18, 0.3], [0.2, 1.25, 1], { extrapolateRight: 'clamp' });
        const op = interpolate(s, [1.0, 1.3], [1, 0], { extrapolateLeft: 'clamp' });
        return <div key={i} style={{ position: 'absolute', top: 1250 - s * 40, [side(e.who)]: 330, fontSize: 150,
          transform: `scale(${sc}) rotate(${Math.sin(s * 9) * 8}deg)`, opacity: op }}>{e.e}</div>;
      })}
      {/* hook */}
      {p.hook && t < p.hook.end ? (
        <div style={{ position: 'absolute', top: TOP + 34, width: 1080, display: 'flex', justifyContent: 'center' }}>
          <div style={{ fontFamily: LILITA, fontSize: 64, color: '#fff', background: '#E8344E', padding: '10px 28px', borderRadius: 18,
            transform: `scale(${interpolate(t, [0, 0.25], [0.6, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(2.5)) })}) rotate(-2deg)`,
            boxShadow: '0 8px 24px rgba(0,0,0,0.45)' }}>{p.hook.text}</div>
        </div>
      ) : null}
      {/* captions */}
      {ch ? (
        <div style={{ position: 'absolute', top: 1060, left: 50, width: 980, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 22px',
          transform: `scale(${interpolate(t, [ch.start, ch.start + 0.1], [0.85, 1], { extrapolateRight: 'clamp' })})` }}>
          {ch.words.map((w, i) => {
            const on = t >= w.start - 0.03;
            return <span key={i} style={{ fontFamily: LILITA, fontSize: 100, lineHeight: 1.08, letterSpacing: 1,
              color: on ? color(w.who) : '#ffffff', WebkitTextStroke: '10px #000', paintOrder: 'stroke fill',
              textShadow: '0 6px 12px rgba(0,0,0,0.5)' }}>{w.text}</span>;
          })}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
