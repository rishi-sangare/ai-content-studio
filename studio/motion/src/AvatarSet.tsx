import React from 'react';
import { AbsoluteFill } from 'remotion';
import { loadFont as loadLilita } from '@remotion/google-fonts/LilitaOne';
import { loadFont as loadBungee } from '@remotion/google-fonts/Bungee';
import { loadFont as loadPress } from '@remotion/google-fonts/PressStart2P';

const { fontFamily: LILITA } = loadLilita();
const { fontFamily: BUNGEE } = loadBungee();
const { fontFamily: PIXEL } = loadPress();

// Four profile-picture directions for Day One Drops (800x800, readable at 48 px in a circle crop).
export type AvatarSetProps = { style: 'monogram' | 'calendar' | 'controller' | 'pixel' };

const Monogram = () => (
  <AbsoluteFill style={{ background: 'linear-gradient(135deg, #6a2cff 0%, #ff3d7f 55%, #ffb321 100%)', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ width: 560, height: 560, borderRadius: 140, background: '#0f0b1a', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 30px 60px rgba(0,0,0,0.35)' }}>
      <div style={{ fontFamily: BUNGEE, fontSize: 300, lineHeight: 1, background: 'linear-gradient(135deg, #b89cff, #ff7fa8 50%, #ffd36b)',
                    WebkitBackgroundClip: 'text', color: 'transparent', letterSpacing: -10 }}>D1</div>
    </div>
  </AbsoluteFill>
);

const Calendar = () => (
  <AbsoluteFill style={{ background: '#ffcf33', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{ width: 520, height: 560, borderRadius: 60, background: '#fff', overflow: 'hidden', boxShadow: '0 22px 0 #1a1a1a', border: '14px solid #1a1a1a',
                  display: 'flex', flexDirection: 'column', transform: 'rotate(-4deg)' }}>
      <div style={{ background: '#ff3b3b', height: 150, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '14px solid #1a1a1a' }}>
        <span style={{ fontFamily: LILITA, fontSize: 104, color: '#fff', letterSpacing: 4 }}>DAY</span>
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: LILITA, fontSize: 330, color: '#1a1a1a', lineHeight: 1 }}>1</span>
      </div>
    </div>
  </AbsoluteFill>
);

const Controller = () => (
  <AbsoluteFill style={{ background: 'radial-gradient(circle at 50% 40%, #1b3cff 0%, #0a1240 75%)', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
    <svg width="560" height="360" viewBox="0 0 280 180">
      <path d="M60 30 h160 a50 50 0 0 1 50 50 v20 a60 60 0 0 1 -105 40 l-10 -12 h-50 l-10 12 a60 60 0 0 1 -105 -40 v-20 a50 50 0 0 1 50 -50 z" fill="#ffffff" />
      <rect x="62" y="70" width="14" height="44" rx="4" fill="#0a1240" /><rect x="47" y="85" width="44" height="14" rx="4" fill="#0a1240" />
      <circle cx="205" cy="76" r="10" fill="#ff3d7f" /><circle cx="225" cy="96" r="10" fill="#ffb321" /><circle cx="185" cy="96" r="10" fill="#38e07b" /><circle cx="205" cy="116" r="10" fill="#38c8ff" />
      <text x="140" y="104" textAnchor="middle" fontFamily={LILITA} fontSize="44" fill="#0a1240">1</text>
    </svg>
    <div style={{ fontFamily: LILITA, fontSize: 104, color: '#fff', letterSpacing: 3, lineHeight: 1 }}>DAY ONE</div>
  </AbsoluteFill>
);

const Pixel = () => {
  const px = 'repeating-linear-gradient(0deg, rgba(0,0,0,0.18) 0 4px, transparent 4px 8px)';
  return (
    <AbsoluteFill style={{ background: `${px}, linear-gradient(180deg, #12002e 0%, #3a0a6b 100%)`, alignItems: 'center', justifyContent: 'center', gap: 34 }}>
      <div style={{ fontFamily: PIXEL, fontSize: 92, color: '#38e07b', textShadow: '8px 8px 0 #0b3d22', lineHeight: 1.2, textAlign: 'center' }}>DAY<br />ONE</div>
      <div style={{ fontFamily: PIXEL, fontSize: 58, color: '#fff', background: '#ff3d7f', padding: '18px 26px', boxShadow: '8px 8px 0 #7a1238' }}>DROPS</div>
    </AbsoluteFill>
  );
};

export const AvatarSet: React.FC<AvatarSetProps> = ({ style }) =>
  style === 'monogram' ? <Monogram /> : style === 'calendar' ? <Calendar /> : style === 'controller' ? <Controller /> : <Pixel />;
