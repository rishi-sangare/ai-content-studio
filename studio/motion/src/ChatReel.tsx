import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, staticFile, interpolate, Easing } from 'remotion';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { Captions, EmojiPops, Body, useT, currentLine, LILITA, CastMember, Word, Line, Emoji } from './Bits';
import { ScreenDemo, DemoProps } from './ScreenDemo';

const { fontFamily: INTER } = loadInter('normal', { weights: ['400', '600', '800'], subsets: ['latin'] });

// Format C "Group chat": a voiced Discord-style channel. Each spoken line lands as a message (typing indicator first);
// links unfurl into embeds with the real page; Jev is a BOT that answers with its real API result (and never speaks — a
// "ding" and text only); GIFs post as messages; reactions pop on. Characters react small at the bottom over the captions.

export type Msg = {
  t: number; who: string; text?: string; face?: string;
  embed?: { site: string; title: string; desc?: string; img?: string };
  result?: { text: string; sub?: string; color?: string };
  gif?: string;
  reactions?: { e: string; t: number; n?: number }[];
};
export type ChatProps = {
  fps: number; duration: number; cast: CastMember[]; words: Word[]; lines: Line[]; amp: number[];
  channel: string; msgs: Msg[]; emojis?: Emoji[];
  // link clicks: the cursor clicks message `msg` at (ox, oy inside it); the real page then opens full-height (ScreenDemo with
  // absolute times) from `start` to `end` and snaps back to the chat
  web?: { click: number; msg: number; ox: number; oy: number; start: number; end: number; demo: DemoProps }[];
};

const NAME: Record<string, string> = { cube: 'Cube', legacy: 'Legacy', jev: 'Jev' };
const TOP = 130, BOTTOM = 1400, LEFT = 150, TEXTW = 880;

function lineCount(text?: string) { return text ? Math.max(1, Math.ceil(text.length / 40)) : 0; }
function msgHeight(m: Msg) {
  return 62 + lineCount(m.text) * 50 + (m.embed ? 400 : 0) + (m.result ? 150 : 0) + (m.gif ? 330 : 0) + (m.reactions?.length ? 66 : 0) + 30;
}

const Avatar: React.FC<{ who: string; face?: string; color: string }> = ({ who, face, color }) => (
  <div style={{ position: 'absolute', left: 30, top: 0, width: 92, height: 92, borderRadius: 92, overflow: 'hidden',
    background: who === 'jev' ? '#7C3AED' : '#2b2d31', border: `3px solid ${color}` }}>
    {who === 'jev'
      ? <div style={{ fontFamily: INTER, fontWeight: 800, fontSize: 56, color: '#fff', textAlign: 'center', lineHeight: '86px' }}>J</div>
      : <Img src={staticFile(`heads/${who}_${face ?? 'neutral'}.png`)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />}
  </div>
);

export const ChatReel: React.FC<ChatProps> = (p) => {
  const t = useT(p.fps);
  const frame = Math.round(t * p.fps);
  const amp = p.amp[Math.min(frame, p.amp.length - 1)] ?? 0;
  const line = currentLine(p.lines, t);
  const speaking = t <= line.end + 0.05 ? line.who : null;
  const color = (w: string) => w === 'jev' ? '#A78BFA' : (p.cast.find((c) => c.id === w)?.color ?? '#fff');

  // layout + auto-scroll: keep the newest message above the caption zone
  const ys: number[] = []; let acc = 0;
  p.msgs.forEach((m) => { ys.push(acc); acc += msgHeight(m); });
  const target = (i: number) => Math.max(0, ys[i] + msgHeight(p.msgs[i]) - (BOTTOM - TOP));
  let scroll = 0;
  p.msgs.forEach((m, i) => {
    if (t >= m.t) scroll = interpolate(t, [m.t, m.t + 0.25], [i ? target(i - 1) : 0, target(i)], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  });
  const next = p.msgs.find((m) => m.t > t && m.t - t < 0.7 && m.who !== 'jev');
  const jevNext = p.msgs.find((m) => m.t > t && m.t - t < 1.2 && m.who === 'jev');

  return (
    <AbsoluteFill style={{ background: '#313338', fontFamily: INTER }}>
      <div style={{ position: 'absolute', top: TOP, left: 0, width: 1080, height: BOTTOM - TOP, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: -scroll + 20, left: 0, width: 1080 }}>
          {p.msgs.map((m, i) => {
            if (t < m.t) return null;
            const s = t - m.t;
            const inP = interpolate(s, [0, 0.18], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
            const live = speaking === m.who && p.msgs.filter((q) => q.who === m.who && q.t <= t).pop() === m;
            const c = color(m.who);
            return (
              <div key={i} style={{ position: 'absolute', top: ys[i], left: 0, width: 1080, height: msgHeight(m) - 10,
                opacity: inP, transform: `translateY(${(1 - inP) * 30}px)`, background: live ? 'rgba(255,255,255,0.05)' : (m.who === 'jev' ? 'rgba(124,58,237,0.10)' : 'transparent') }}>
                <div style={{ position: 'absolute', top: 14, left: 0 }}><Avatar who={m.who} face={m.face} color={c} /></div>
                <div style={{ position: 'absolute', top: 12, left: LEFT, width: TEXTW }}>
                  <span style={{ fontWeight: 800, fontSize: 38, color: c }}>{NAME[m.who] ?? m.who}</span>
                  {m.who === 'jev' ? <span style={{ marginLeft: 12, background: '#5865F2', color: '#fff', fontSize: 22, fontWeight: 800, padding: '3px 8px', borderRadius: 6, verticalAlign: 6 }}>✓ BOT</span> : null}
                  <span style={{ marginLeft: 14, fontSize: 24, color: '#949BA4' }}>Today at 9:41 PM</span>
                  {m.text ? <div style={{ fontSize: 40, lineHeight: '50px', color: '#DBDEE1', marginTop: 4, fontWeight: 400 }}>
                    {m.text.split(/(@\w+)/).map((part, k) => part.startsWith('@')
                      ? <span key={k} style={{ background: 'rgba(88,101,242,0.3)', color: '#C9CDFB', borderRadius: 6, padding: '0 4px' }}>{part}</span> : part)}
                  </div> : null}
                  {m.embed ? (
                    <div style={{ marginTop: 12, width: 820, background: '#2B2D31', borderLeft: '8px solid #7C3AED', borderRadius: 10, padding: '18px 22px' }}>
                      <div style={{ fontSize: 24, color: '#B5BAC1' }}>{m.embed.site}</div>
                      <div style={{ fontSize: 34, fontWeight: 800, color: '#00A8FC', margin: '6px 0' }}>{m.embed.title}</div>
                      {m.embed.desc ? <div style={{ fontSize: 28, color: '#DBDEE1' }}>{m.embed.desc}</div> : null}
                      {m.embed.img ? <Img src={staticFile(m.embed.img)} style={{ marginTop: 12, width: 520, borderRadius: 8, display: 'block' }} /> : null}
                    </div>
                  ) : null}
                  {m.result ? (
                    <div style={{ marginTop: 12, width: 760, background: '#2B2D31', borderLeft: `8px solid ${m.result.color ?? '#ED4245'}`, borderRadius: 10, padding: '16px 22px',
                      transform: `scale(${interpolate(s, [0, 0.12, 0.22], [0.8, 1.06, 1], { extrapolateRight: 'clamp' })})`, transformOrigin: 'left center' }}>
                      <div style={{ fontFamily: LILITA, fontSize: 76, color: m.result.color ?? '#ED4245', lineHeight: 1 }}>{m.result.text}</div>
                      {m.result.sub ? <div style={{ fontSize: 30, color: '#DBDEE1', marginTop: 6 }}>{m.result.sub}</div> : null}
                    </div>
                  ) : null}
                  {m.gif ? (
                    <div style={{ marginTop: 12, width: 440, height: 300, borderRadius: 10, overflow: 'hidden' }}>
                      <OffthreadVideo src={staticFile(m.gif)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                  ) : null}
                  {m.reactions?.length ? (
                    <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                      {m.reactions.filter((r) => t >= r.t).map((r, k) => (
                        <div key={k} style={{ background: '#3C3F45', border: '2px solid #5865F2', borderRadius: 12, padding: '4px 12px', fontSize: 30, color: '#DBDEE1',
                          transform: `scale(${interpolate(t - r.t, [0, 0.12, 0.2], [0.3, 1.2, 1], { extrapolateRight: 'clamp' })})` }}>{r.e} {r.n ?? 1}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* channel header */}
      <div style={{ position: 'absolute', top: 0, left: 0, width: 1080, height: TOP, background: '#2B2D31', borderBottom: '2px solid #1F2023',
        display: 'flex', alignItems: 'center', padding: '0 36px', gap: 18 }}>
        <span style={{ fontSize: 54, color: '#80848E', fontWeight: 600 }}>#</span>
        <span style={{ fontSize: 42, color: '#F2F3F5', fontWeight: 800 }}>{p.channel}</span>
        <span style={{ marginLeft: 'auto', fontSize: 28, color: '#949BA4' }}>🟢 3 online</span>
      </div>
      {/* typing indicator */}
      {next || jevNext ? (
        <div style={{ position: 'absolute', top: BOTTOM - 4, left: 36, fontSize: 28, color: '#DBDEE1', fontWeight: 600 }}>
          <span style={{ letterSpacing: 4 }}>{'•••'.slice(0, 1 + (Math.floor(t * 6) % 3))}</span>{' '}
          {NAME[(next ?? jevNext)!.who]} is {(next ?? jevNext)!.who === 'jev' ? 'deciding' : 'typing'}…
        </div>
      ) : null}
      {/* chat cursor clicking a link */}
      {(p.web ?? []).filter((w) => t >= w.click - 0.6 && t < w.start + 0.05).map((w, i) => {
        const tx = LEFT + w.ox, ty = TOP + 20 + ys[w.msg] - scroll + w.oy;
        const k = interpolate(t, [w.click - 0.6, w.click - 0.1], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic) });
        const x = 950 + (tx - 950) * k, y = 1320 + (ty - 1320) * k, since = t - w.click;
        return (
          <React.Fragment key={i}>
            {since >= 0 ? <div style={{ position: 'absolute', left: x - 40, top: y - 40, width: 80, height: 80, borderRadius: 40, border: '5px solid rgba(88,101,242,0.95)',
              transform: `scale(${interpolate(since, [0, 0.3], [0.3, 1.4], { extrapolateRight: 'clamp' })})`, opacity: interpolate(since, [0, 0.3], [1, 0], { extrapolateRight: 'clamp' }) }} /> : null}
            <svg width={60} height={60} viewBox="0 0 24 24" style={{ position: 'absolute', left: x - 8, top: y - 5, transform: `scale(${since >= 0 && since < 0.12 ? 0.82 : 1})`,
              filter: 'drop-shadow(0 3px 4px rgba(0,0,0,0.5))' }}>
              <path d="M5 2 L5 20 L9.5 15.8 L12.6 22.4 L15.4 21.1 L12.4 14.7 L18.6 14.4 Z" fill="#fff" stroke="#111" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </React.Fragment>
        );
      })}
      {/* the opened page (real site, scrolled + clicked), zooms out of the link and back */}
      {(p.web ?? []).filter((w) => t >= w.start && t < w.end).map((w, i) => {
        const inP = interpolate(t, [w.start, w.start + 0.25], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
        const outP = interpolate(t, [w.end - 0.2, w.end], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic) });
        const sc = 0.45 + 0.55 * inP - 0.5 * outP;
        return (
          <div key={i} style={{ position: 'absolute', left: 0, top: 0, width: 1080, height: BOTTOM + 40, background: `rgba(10,10,14,${0.75 * (inP - outP)})` }}>
            <div style={{ position: 'absolute', left: 0, top: 0, width: 1080, height: BOTTOM + 40, transform: `scale(${sc})`, opacity: Math.min(1, inP * 1.5) * (1 - outP),
              transformOrigin: '50% 40%' }}>
              <ScreenDemo {...w.demo} width={1080} height={BOTTOM + 40} />
            </div>
          </div>
        );
      })}
      {/* bottom: reacting characters + big captions */}
      <div style={{ position: 'absolute', top: BOTTOM + 40, left: 0, width: 1080, height: 1920 - BOTTOM - 40,
        background: 'linear-gradient(180deg, #232428 0%, #1a1b1e 100%)', borderTop: '2px solid #1F2023' }} />
      {p.cast.map((c) => (
        <Body key={c.id} c={{ ...c, height: c.id === 'cube' ? 300 : 380 }} face={line.faces[c.id] ?? 'neutral'} speaking={speaking === c.id}
          amp={speaking === c.id ? amp : 0} since={t - line.start} />
      ))}
      <Captions words={p.words} t={t} y={BOTTOM + 70} color={color} size={88} />
      <EmojiPops emojis={p.emojis ?? []} t={t} />
    </AbsoluteFill>
  );
};
