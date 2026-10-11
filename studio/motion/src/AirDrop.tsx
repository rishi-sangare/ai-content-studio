import React from 'react';
import { AbsoluteFill } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';

const { fontFamily: LILITA } = loadLilita();

// Day One Drops profile picture: a supply crate parachuting in ("a drop is coming"), with "1" stamped on the crate.
export type AirDropProps = { withText: boolean };

export const Drop: React.FC<{ scale: number }> = ({ scale }) => (
  <svg width={520 * scale} height={560 * scale} viewBox="0 0 260 280">
    {/* parachute canopy: alternating panels */}
    <defs>
      <clipPath id="canopy"><path d="M20 92 Q130 -40 240 92 Q212 80 185 92 Q157 80 130 92 Q103 80 75 92 Q48 80 20 92 Z" /></clipPath>
    </defs>
    <g clipPath="url(#canopy)">
      <rect x="0" y="0" width="260" height="100" fill="#ff5a36" />
      <rect x="47" y="0" width="28" height="100" fill="#ffffff" />
      <rect x="102" y="0" width="28" height="100" fill="#ffffff" />
      <rect x="157" y="0" width="28" height="100" fill="#ffffff" />
      <rect x="212" y="0" width="28" height="100" fill="#ffffff" />
    </g>
    <path d="M20 92 Q130 -40 240 92 Q212 80 185 92 Q157 80 130 92 Q103 80 75 92 Q48 80 20 92 Z" fill="none" stroke="#1a1a1a" strokeWidth="6" strokeLinejoin="round" />
    {/* lines */}
    <g stroke="#1a1a1a" strokeWidth="4" strokeLinecap="round">
      <line x1="22" y1="92" x2="88" y2="168" /><line x1="75" y1="92" x2="104" y2="168" />
      <line x1="185" y1="92" x2="156" y2="168" /><line x1="238" y1="92" x2="172" y2="168" /><line x1="130" y1="92" x2="130" y2="168" />
    </g>
    {/* crate */}
    <g transform="rotate(-6 130 214)">
      <rect x="76" y="166" width="108" height="96" rx="8" fill="#ffc21a" stroke="#1a1a1a" strokeWidth="7" />
      <rect x="76" y="166" width="108" height="20" fill="#e59a00" stroke="#1a1a1a" strokeWidth="7" />
      <line x1="84" y1="194" x2="176" y2="254" stroke="#e59a00" strokeWidth="9" />
      <text x="130" y="246" textAnchor="middle" fontFamily={LILITA} fontSize="62" fill="#1a1a1a">1</text>
    </g>
    {/* speed lines */}
    <g stroke="#ffffff" strokeWidth="5" strokeLinecap="round" opacity="0.85">
      <line x1="40" y1="150" x2="40" y2="185" /><line x1="224" y1="140" x2="224" y2="178" /><line x1="56" y1="210" x2="56" y2="236" />
    </g>
  </svg>
);

export const AirDrop: React.FC<AirDropProps> = ({ withText }) => (
  <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 30%, #3fb4ff 0%, #1565d8 60%, #0b3a8c 100%)', alignItems: 'center',
                         justifyContent: withText ? 'flex-start' : 'center', paddingTop: withText ? 70 : 0 }}>
    <Drop scale={withText ? 1.0 : 1.3} />
    {withText ? (
      <div style={{ fontFamily: LILITA, fontSize: 118, color: '#fff', lineHeight: 1, marginTop: -6, letterSpacing: 3,
                    WebkitTextStroke: '12px #0b2a66', paintOrder: 'stroke fill' }}>DAY ONE</div>
    ) : null}
  </AbsoluteFill>
);

// Matching YouTube banner (2560x1440): everything important inside the 1546x423 safe area in the middle.
export const AirDropBanner: React.FC = () => (
  <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 40%, #3fb4ff 0%, #1565d8 55%, #0b3a8c 100%)', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 40 }}>
      <Drop scale={0.78} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontFamily: LILITA, fontSize: 150, color: '#fff', lineHeight: 0.95, letterSpacing: 2, WebkitTextStroke: '14px #0b2a66', paintOrder: 'stroke fill' }}>
          DAY ONE <span style={{ color: '#ffc21a' }}>DROPS</span>
        </div>
        <div style={{ fontFamily: LILITA, fontSize: 54, color: '#e8f3ff', letterSpacing: 3 }}>NEW GAMES · FIRST LOOKS · LAUNCH DAY</div>
      </div>
    </div>
  </AbsoluteFill>
);
