import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: MONO } = loadMono('normal', { weights: ['800'], subsets: ['latin'] });
const { fontFamily: INTER } = loadInter('normal', { weights: ['600', '800'], subsets: ['latin'] });
const { fontFamily: LILITA } = loadLilita();

// "Deprecated" (@deprecated.ai) channel art. The wordmark is styled like a deprecated API in an IDE: monospace + strikethrough.
// Avatars must read at ~40 px, so they are faces + one strong shape, no small text.

const BLURPLE = '#5865F2', PURPLE = '#7C3AED', RED = '#ED4245', CYAN = '#4FE3F0', AMBER = '#FFC046';

const Word: React.FC<{ size: number; color?: string }> = ({ size, color = '#fff' }) => (
  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: size, color, letterSpacing: -size * 0.03, position: 'relative', display: 'inline-block', lineHeight: 1 }}>
    deprecated
    <span style={{ position: 'absolute', left: -size * 0.02, right: size * 0.02, top: '54%', height: size * 0.11, background: RED, borderRadius: size, transform: 'rotate(-2deg)' }} />
  </span>
);

export type DepAvatarProps = { variant: 'duo' | 'legacy' | 'strike' };

export const DepAvatar: React.FC<DepAvatarProps> = ({ variant }) => {
  const ring = { position: 'absolute' as const, inset: 0, borderRadius: '50%' };
  if (variant === 'strike') {
    return (
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 30%, #2b2d31, #111214 75%)`, alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ ...ring, inset: 40, border: `22px solid ${BLURPLE}` }} />
        <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 250, color: '#fff', position: 'relative', letterSpacing: -10 }}>
          dep<span style={{ position: 'absolute', left: -14, right: -14, top: '52%', height: 30, background: RED, borderRadius: 30, transform: 'rotate(-4deg)' }} />
        </span>
        <div style={{ position: 'absolute', bottom: 150, fontFamily: MONO, fontWeight: 800, fontSize: 64, color: CYAN }}>.ai</div>
      </AbsoluteFill>
    );
  }
  if (variant === 'legacy') {
    return (
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 38%, ${BLURPLE} 0%, ${PURPLE} 60%, #2a1361 100%)` }}>
        <Img src={staticFile('heads/legacy_smug.png')} style={{ position: 'absolute', left: 95, top: 120, width: 610,
          filter: 'drop-shadow(0 0 0 #fff) drop-shadow(6px 0 0 #fff) drop-shadow(-6px 0 0 #fff) drop-shadow(0 6px 0 #fff) drop-shadow(0 -6px 0 #fff) drop-shadow(0 18px 24px rgba(0,0,0,0.45))' }} />
        <div style={{ position: 'absolute', right: 70, top: 70, width: 190, height: 190, borderRadius: 190, background: RED, border: '16px solid #fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: INTER, fontWeight: 800, fontSize: 110, color: '#fff', boxShadow: '0 10px 30px rgba(0,0,0,0.35)' }}>1</div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 30%, ${BLURPLE} 0%, ${PURPLE} 62%, #2a1361 100%)` }}>
      <Img src={staticFile('heads/legacy_smug.png')} style={{ position: 'absolute', left: 40, top: 120, width: 560,
        filter: 'drop-shadow(6px 0 0 #fff) drop-shadow(-6px 0 0 #fff) drop-shadow(0 6px 0 #fff) drop-shadow(0 -6px 0 #fff) drop-shadow(0 18px 24px rgba(0,0,0,0.45))' }} />
      <Img src={staticFile('heads/cube_talk.png')} style={{ position: 'absolute', right: 26, top: 420, width: 300,
        filter: 'drop-shadow(5px 0 0 #fff) drop-shadow(-5px 0 0 #fff) drop-shadow(0 5px 0 #fff) drop-shadow(0 -5px 0 #fff) drop-shadow(0 14px 20px rgba(0,0,0,0.45))' }} />
    </AbsoluteFill>
  );
};

const Bubble: React.FC<{ who: string; color: string; text?: string; result?: string; resultColor?: string; head?: string; jev?: boolean }> = ({ who, color, text, result, resultColor, head, jev }) => (
  <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start', marginBottom: 26 }}>
    <div style={{ width: 84, height: 84, borderRadius: 84, overflow: 'hidden', background: jev ? PURPLE : '#2b2d31', border: `3px solid ${color}`, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: INTER, fontWeight: 800, fontSize: 48, color: '#fff' }}>
      {jev ? 'J' : <Img src={staticFile(`heads/${head}.png`)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />}
    </div>
    <div>
      <div style={{ fontFamily: INTER, fontWeight: 800, fontSize: 32, color }}>{who}
        {jev ? <span style={{ marginLeft: 10, background: BLURPLE, color: '#fff', fontSize: 20, padding: '2px 8px', borderRadius: 6, verticalAlign: 5 }}>✓ BOT</span> : null}
      </div>
      {text ? <div style={{ fontFamily: INTER, fontWeight: 600, fontSize: 34, color: '#DBDEE1' }}>{text}</div> : null}
      {result ? <div style={{ marginTop: 6, fontFamily: LILITA, fontSize: 56, color: resultColor, background: '#2b2d31', borderLeft: `7px solid ${resultColor}`, padding: '4px 18px', borderRadius: 8 }}>{result}</div> : null}
    </div>
  </div>
);

export const DepBanner: React.FC = () => (
  // 2560x1440; YouTube's always-visible safe area is the centre 1546x423 (x 507–2053, y 508–931)
  <AbsoluteFill style={{ background: '#111214' }}>
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 30% 50%, rgba(88,101,242,0.35), transparent 55%), radial-gradient(ellipse at 80% 60%, rgba(124,58,237,0.30), transparent 50%),
      repeating-linear-gradient(0deg, rgba(255,255,255,0.03) 0 2px, transparent 2px 72px), repeating-linear-gradient(90deg, rgba(255,255,255,0.03) 0 2px, transparent 2px 72px)` }} />
    {/* characters live outside the safe area: seen on desktop + TV, cropped on phones */}
    <Img src={staticFile('chars/legacy_smug.png')} style={{ position: 'absolute', left: 10, top: 470, height: 640, filter: 'drop-shadow(0 20px 30px rgba(0,0,0,0.6))' }} />
    <Img src={staticFile('chars/cube_talk.png')} style={{ position: 'absolute', right: 30, top: 600, height: 470, filter: 'drop-shadow(0 20px 30px rgba(0,0,0,0.6))' }} />
    {/* safe area content */}
    <div style={{ position: 'absolute', left: 540, top: 520, width: 1000, height: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <div style={{ fontFamily: MONO, fontWeight: 800, fontSize: 30, color: '#949BA4', marginBottom: 14 }}># ai-news-drops</div>
      <Word size={168} />
      <div style={{ fontFamily: INTER, fontWeight: 800, fontSize: 50, color: '#fff', marginTop: 26 }}>
        AI news, <span style={{ color: CYAN }}>before it replaces us.</span>
      </div>
      <div style={{ fontFamily: INTER, fontWeight: 600, fontSize: 32, color: '#B5BAC1', marginTop: 12 }}>New AI drops · tested live · the catch · daily</div>
    </div>
    <div style={{ position: 'absolute', left: 1560, top: 545, width: 480 }}>
      <Bubble who="Cube" color={CYAN} head="cube_talk" text="@Jev is Legacy getting replaced?" />
      <Bubble who="Jev" color="#A78BFA" jev result="✅ YES · 75%" resultColor="#23A55A" />
    </div>
  </AbsoluteFill>
);
