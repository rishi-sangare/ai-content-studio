import React from 'react';
import { AbsoluteFill } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: LILITA } = loadLilita();

// Channel art for a page: profile picture (square) or banner (2560x1440, text inside YouTube's 1546x423 safe area).
export type BrandProps = { kind: 'avatar' | 'banner'; line1: string; line2: string; tag?: string; accent?: string; bg?: string };

const Mark: React.FC<{ size: number; accent: string }> = ({ size, accent }) => (
  // a launch "drop" pin: a downward chevron in a ring, reads at 98 px
  <svg width={size} height={size} viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="44" fill="none" stroke={accent} strokeWidth="9" />
    <path d="M30 38 L50 62 L70 38" fill="none" stroke="#ffffff" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Brand: React.FC<BrandProps> = ({ kind, line1, line2, tag, accent = '#38E07B', bg = '#101418' }) => {
  const grid = `repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0 2px, transparent 2px 64px), repeating-linear-gradient(90deg, rgba(255,255,255,0.035) 0 2px, transparent 2px 64px)`;
  if (kind === 'avatar') {
    return (
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 35%, #1f2a33 0%, ${bg} 70%)`, alignItems: 'center', justifyContent: 'center', gap: 18 }}>
        <Mark size={300} accent={accent} />
        <div style={{ fontFamily: LILITA, fontSize: 132, color: '#fff', lineHeight: 0.9, textAlign: 'center' }}>
          {line1}<br /><span style={{ color: accent }}>{line2}</span>
        </div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: `${grid}, linear-gradient(120deg, ${bg} 0%, #17222b 60%, #0c1013 100%)`, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 48 }}>
        <Mark size={210} accent={accent} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontFamily: LILITA, fontSize: 150, color: "#fff", lineHeight: 0.92, letterSpacing: 2 }}>
            {line1} <span style={{ color: accent }}>{line2}</span>
          </div>
          {tag ? <div style={{ fontFamily: LILITA, fontSize: 52, color: "#c9d4dc", letterSpacing: 3 }}>{tag}</div> : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
