import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: LILITA } = loadLilita();

// Reel / Short cover (1080x1920). Everything important sits inside the centre 3:4 band (y 240–1680),
// because Instagram's profile grid crops the cover to 3:4.
export type CoverProps = { bg: string; logo?: string; line1: string; line2?: string; accent?: string; bgScale?: number; bgY?: number };

export const Cover: React.FC<CoverProps> = ({ bg, logo, line1, line2, accent = '#FFD23F', bgScale = 1.0, bgY = 0 }) => (
  <AbsoluteFill style={{ backgroundColor: '#0b0b10' }}>
    <AbsoluteFill style={{ transform: `scale(${bgScale}) translateY(${bgY}px)` }}>
      <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </AbsoluteFill>
    <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 60%, rgba(5,5,10,0.95) 76%, rgba(5,5,10,0.97) 100%)' }} />
    <AbsoluteFill style={{ alignItems: 'center', top: 300, height: 'auto' }}>
      <div style={{ fontFamily: LILITA, fontSize: 132, lineHeight: 1.0, color: accent, textAlign: 'center', letterSpacing: 2,
                    WebkitTextStroke: '14px #111', paintOrder: 'stroke fill', textShadow: '0 10px 0 rgba(0,0,0,0.55)', maxWidth: 1000 }}>
        {line1}
      </div>
      {line2 ? <div style={{ fontFamily: LILITA, fontSize: 104, lineHeight: 1.05, color: '#fff', textAlign: 'center', marginTop: 10,
                    WebkitTextStroke: '12px #111', paintOrder: 'stroke fill', textShadow: '0 9px 0 rgba(0,0,0,0.55)', maxWidth: 1000 }}>
        {line2}
      </div> : null}
    </AbsoluteFill>
    {logo ? <AbsoluteFill style={{ alignItems: 'center', top: 1330, height: 'auto' }}>
      <Img src={staticFile(logo)} style={{ width: 760, filter: 'drop-shadow(0 10px 18px rgba(0,0,0,0.6))' }} />
    </AbsoluteFill> : null}
  </AbsoluteFill>
);
