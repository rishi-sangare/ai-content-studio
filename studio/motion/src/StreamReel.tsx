import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { ScreenDemo, DemoProps } from './ScreenDemo';
import { Captions, GifPops, EmojiPops, HudBar, Chip, useT, currentLine, LILITA, CastMember, Word, Line, Gif, Emoji, Hud } from './Bits';

// Format A "Stream": the real site fills the whole screen like a streamer's screen-share; the two characters are round
// facecams in the bottom corners (speaker's ring glows and pulses with the voice, listener dims), LIVE badge + stream title.

export type StreamProps = {
  fps: number; duration: number; demo: DemoProps; cast: CastMember[]; words: Word[]; lines: Line[]; amp: number[];
  gifs?: Gif[]; emojis?: Emoji[]; hud?: Hud[]; title: string; hook?: { text: string; end: number };
};

const Cam: React.FC<{ c: CastMember; face: string; speaking: boolean; amp: number; size: number }> = ({ c, face, speaking, amp, size }) => {
  const ring = speaking ? 10 + amp * 8 : 6;
  return (
    <div style={{ position: 'absolute', bottom: 70, [c.side]: 34, width: size, height: size, borderRadius: size,
      border: `${ring}px solid ${c.color}`, boxShadow: speaking ? `0 0 ${30 + amp * 40}px ${c.color}` : '0 10px 30px rgba(0,0,0,0.6)',
      background: 'radial-gradient(circle at 50% 35%, #3a3f55, #151821)', overflow: 'hidden',
      transform: `scale(${speaking ? 1 + amp * 0.04 : 0.9})`, filter: `brightness(${speaking ? 1 : 0.65})` }}>
      <Img src={staticFile(`heads/${c.id}_${face}.png`)} style={{ position: 'absolute', left: '6%', top: '8%', width: '88%', height: '88%', objectFit: 'contain' }} />
      <div style={{ position: 'absolute', bottom: 10, width: '100%', textAlign: 'center', fontFamily: LILITA, fontSize: 30, color: '#fff',
        textShadow: '0 2px 6px #000' }}>{c.id.toUpperCase()}</div>
    </div>
  );
};

export const StreamReel: React.FC<StreamProps> = (p) => {
  const t = useT(p.fps);
  const frame = Math.round(t * p.fps);
  const amp = p.amp[Math.min(frame, p.amp.length - 1)] ?? 0;
  const line = currentLine(p.lines, t);
  const speaking = t <= line.end + 0.05 ? line.who : null;
  const color = (w: string) => p.cast.find((c) => c.id === w)?.color ?? '#fff';
  return (
    <AbsoluteFill style={{ background: '#101218' }}>
      <ScreenDemo {...p.demo} width={1080} height={1920} />
      {/* stream overlay */}
      <div style={{ position: 'absolute', top: 120, left: 40, display: 'flex', gap: 14, alignItems: 'center' }}>
        <div style={{ background: '#E8283C', color: '#fff', fontFamily: LILITA, fontSize: 40, padding: '4px 18px', borderRadius: 10,
          opacity: Math.floor(t * 1.5) % 2 === 0 ? 1 : 0.75 }}>● LIVE</div>
        <div style={{ background: 'rgba(0,0,0,0.75)', color: '#fff', fontFamily: LILITA, fontSize: 36, padding: '6px 18px', borderRadius: 10 }}>{p.title}</div>
      </div>
      <HudBar hud={p.hud ?? []} t={t} x={40} y={200} />
      {p.hook && t < p.hook.end ? (
        <div style={{ position: 'absolute', top: 205, left: 40 }}><Chip text={p.hook.text} t={t} size={58} /></div>
      ) : null}
      {/* bottom shade so captions + cams read over the page */}
      <div style={{ position: 'absolute', bottom: 0, width: 1080, height: 860, background: 'linear-gradient(180deg, rgba(8,8,12,0) 0%, rgba(8,8,12,0.88) 22%, rgba(8,8,12,0.94) 100%)' }} />
      {p.cast.map((c) => (
        <Cam key={c.id} c={c} face={line.faces[c.id] ?? 'neutral'} speaking={speaking === c.id} amp={speaking === c.id ? amp : 0} size={c.id === 'cube' ? 330 : 310} />
      ))}
      <Captions words={p.words} t={t} y={1215} color={color} size={104} />
      <GifPops gifs={p.gifs ?? []} fps={p.fps} t={t} />
      <EmojiPops emojis={p.emojis ?? []} t={t} />
    </AbsoluteFill>
  );
};
