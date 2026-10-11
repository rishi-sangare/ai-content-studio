import React from 'react';
import { AbsoluteFill, Img, staticFile, interpolate, Easing } from 'remotion';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { Parkour } from './Parkour';
import { Captions, GifPops, EmojiPops, HudBar, Chip, Body, useT, currentLine, LILITA, CastMember, Word, Line, Gif, Emoji, Hud } from './Bits';

const { fontFamily: INTER } = loadInter('normal', { weights: ['600', '800'], subsets: ['latin'] });

// Format B "Floating cards": full-screen voxel parkour, one big card per idea slams in (screenshot of the real page or a
// stat/answer card), tilts, then flies out; characters stand at the bottom; captions in the middle.

export type Card = {
  start: number; end: number; y: number; rot?: number;
  img?: string; label?: string;                          // screenshot card (+ small caption under it)
  tag?: string; text?: string; sub?: string; color?: string;   // stat / answer card
  w?: number;
};
export type CardsProps = {
  fps: number; duration: number; cast: CastMember[]; words: Word[]; lines: Line[]; amp: number[];
  cards: Card[]; gifs?: Gif[]; emojis?: Emoji[]; hud?: Hud[]; chip?: string; seed?: number;
};

const CardView: React.FC<{ c: Card; t: number }> = ({ c, t }) => {
  const s = t - c.start, left = c.end - t;
  const inP = interpolate(s, [0, 0.22], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.8)) });
  const outP = interpolate(left, [0, 0.18], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic) });
  const w = c.w ?? 940;
  const rot = (c.rot ?? -2) + (1 - inP) * 10 + outP * -8;
  const sc = 0.4 + 0.6 * inP + Math.sin(s * 2.2) * 0.008;
  return (
    <div style={{ position: 'absolute', left: (1080 - w) / 2, top: c.y - outP * 900, width: w, transform: `rotate(${rot}deg) scale(${sc})`,
      opacity: Math.min(1, inP * 2), filter: 'drop-shadow(0 26px 40px rgba(0,0,0,0.55))' }}>
      {c.img ? (
        <div style={{ background: '#fff', borderRadius: 28, padding: 14, border: '6px solid #fff' }}>
          <Img src={staticFile(c.img)} style={{ width: '100%', borderRadius: 18, display: 'block' }} />
          {c.label ? <div style={{ fontFamily: INTER, fontWeight: 800, fontSize: 34, color: '#111', padding: '14px 10px 4px' }}>{c.label}</div> : null}
        </div>
      ) : (
        <div style={{ background: '#111', borderRadius: 30, padding: '28px 30px', border: `6px solid ${c.color ?? '#FF4D4D'}`, textAlign: 'center' }}>
          {c.tag ? <div style={{ fontFamily: INTER, fontWeight: 600, fontSize: 30, color: '#aaa', letterSpacing: 3 }}>{c.tag}</div> : null}
          <div style={{ fontFamily: LILITA, fontSize: 110, color: c.color ?? '#FF4D4D', lineHeight: 1.05 }}>{c.text}</div>
          {c.sub ? <div style={{ fontFamily: INTER, fontWeight: 800, fontSize: 40, color: '#fff', marginTop: 8 }}>{c.sub}</div> : null}
        </div>
      )}
    </div>
  );
};

export const CardsReel: React.FC<CardsProps> = (p) => {
  const t = useT(p.fps);
  const frame = Math.round(t * p.fps);
  const amp = p.amp[Math.min(frame, p.amp.length - 1)] ?? 0;
  const line = currentLine(p.lines, t);
  const speaking = t <= line.end + 0.05 ? line.who : null;
  const color = (w: string) => p.cast.find((c) => c.id === w)?.color ?? '#fff';
  return (
    <AbsoluteFill style={{ background: '#8fcbff' }}>
      <Parkour width={1080} height={1920} seed={p.seed ?? 11} duration={p.duration} />
      {p.chip ? <div style={{ position: 'absolute', top: 70, left: 40 }}><Chip text={p.chip} t={t} size={56} /></div> : null}
      <HudBar hud={p.hud ?? []} t={t} x={40} y={160} />
      {p.cards.filter((c) => t >= c.start && t < c.end).map((c, i) => <CardView key={i} c={c} t={t} />)}
      {p.cast.map((c) => (
        <Body key={c.id} c={c} face={line.faces[c.id] ?? 'neutral'} speaking={speaking === c.id} amp={speaking === c.id ? amp : 0} since={t - line.start} />
      ))}
      <Captions words={p.words} t={t} y={1010} color={color} size={104} />
      <GifPops gifs={p.gifs ?? []} fps={p.fps} t={t} />
      <EmojiPops emojis={p.emojis ?? []} t={t} />
    </AbsoluteFill>
  );
};
