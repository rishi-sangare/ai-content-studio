import React from 'react';
import { Composition } from 'remotion';
import { Overlay, OverlayProps } from './Overlay';
import { Cover, CoverProps } from './Cover';
import { Brand, BrandProps } from './Brand';
import { AvatarSet, AvatarSetProps } from './AvatarSet';
import { AirDrop, AirDropProps, AirDropBanner } from './AirDrop';
import { ScreenDemo, DemoProps } from './ScreenDemo';
import { Parkour, ParkourProps } from './Parkour';
import { NewsReel, ReelProps } from './NewsReel';
import { StreamReel, StreamProps } from './StreamReel';
import { CardsReel, CardsProps } from './CardsReel';
import { ChatReel, ChatProps } from './ChatReel';
import { DepAvatar, DepAvatarProps, DepBanner } from './DeprecatedBrand';

// One transparent 1080x1920 layer per Short: captions + titles + stamps. ffmpeg lays it over the edit.
// Props come from the recipe (studio/render/motion.py writes them); duration follows the props.
const defaults: OverlayProps = {
  fps: 30,
  duration: 3,
  words: [
    { text: 'This', start: 0.1, end: 0.3 },
    { text: 'Roblox', start: 0.3, end: 0.7, hl: true },
    { text: 'game', start: 0.7, end: 1.0 },
    { text: 'comes', start: 1.1, end: 1.4 },
    { text: 'out', start: 1.4, end: 1.6 },
    { text: 'October', start: 1.6, end: 2.0, hl: true },
    { text: '17', start: 2.0, end: 2.4, hl: true },
  ],
  titles: [{ text: 'COMING OCT 17', start: 0.2, end: 2.8, kind: 'stamp', y: 0.2 }],
  style: { y: 0.66, accent: '#FFD23F', accent2: '#7CFF6B' },
};

export const Root: React.FC = () => (
  <>
  <Composition
    id="Overlay"
    component={Overlay}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={90}
    defaultProps={defaults}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.max(1, Math.round(props.duration * props.fps)),
      fps: props.fps,
    })}
  />
  <Composition id="Cover" component={Cover} width={1080} height={1920} fps={30} durationInFrames={1}
    defaultProps={{ bg: 'cover/sv001_bg.png', logo: 'cover/sv_logo.png', line1: "GRANDPA'S LETTER", line2: 'HAD A SECRET…' } as CoverProps} />
  <Composition id="BrandAvatar" component={Brand} width={800} height={800} fps={30} durationInFrames={1}
    defaultProps={{ kind: 'avatar', line1: 'DAY ONE', line2: 'DROPS' } as BrandProps} />
  <Composition id="BrandBanner" component={Brand} width={2560} height={1440} fps={30} durationInFrames={1}
    defaultProps={{ kind: 'banner', line1: 'DAY ONE', line2: 'DROPS', tag: 'NEW GAMES · FIRST LOOKS · LAUNCH DAY' } as BrandProps} />
  <Composition id="AvatarSet" component={AvatarSet} width={800} height={800} fps={30} durationInFrames={1}
    defaultProps={{ style: 'monogram' } as AvatarSetProps} />
  <Composition id="AirDrop" component={AirDrop} width={800} height={800} fps={30} durationInFrames={1}
    defaultProps={{ withText: true } as AirDropProps} />
  <Composition id="ScreenDemo" component={ScreenDemo} width={1080} height={900} fps={30} durationInFrames={90}
    defaultProps={{ fps: 30, duration: 3, scenes: [{ start: 0, end: 3, img: 'web/typesafe_ai.png', imgH: 4800, url: 'typesafe.ai' }],
      cam: [{ t: 0, x: 540, y: 420 }], cursor: [{ t: 0, x: 540, y: 400 }], clicks: [] } as DemoProps}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duration * props.fps)), fps: props.fps,
      width: props.width ?? 1080, height: props.height ?? 900 })} />
  <Composition id="Parkour" component={Parkour} width={1080} height={1020} fps={30} durationInFrames={300}
    defaultProps={{ width: 1080, height: 1020, seed: 7, duration: 10 } as ParkourProps}
    calculateMetadata={({ props }) => ({ width: props.width, height: props.height, durationInFrames: Math.round(props.duration * 30) })} />
  <Composition id="NewsReel" component={NewsReel} width={1080} height={1920} fps={30} durationInFrames={90}
    defaultProps={{ fps: 30, duration: 3, demo: { fps: 30, duration: 3, scenes: [{ start: 0, end: 3, img: 'web/typesafe_ai.png', imgH: 4800, url: 'typesafe.ai' }],
      cam: [{ t: 0, x: 540, y: 420 }], cursor: [{ t: 0, x: 540, y: 400 }], clicks: [] }, words: [], lines: [{ start: 0, end: 3, who: 'miko', miko: 'talk', ren: 'neutral' }], amp: [] } as ReelProps}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duration * props.fps)), fps: props.fps })} />
  <Composition id="StreamReel" component={StreamReel} width={1080} height={1920} fps={30} durationInFrames={60}
    defaultProps={{ fps: 30, duration: 2, cast: [], words: [], lines: [{ start: 0, end: 2, who: 'cube', faces: {} }], amp: [], title: '', demo: { fps: 30, duration: 2, scenes: [{ start: 0, end: 2, img: 'web/typesafe_ai.png', imgH: 4800, url: 'typesafe.ai' }], cam: [{ t: 0, x: 540, y: 900 }], cursor: [{ t: 0, x: 540, y: 900 }], clicks: [] } } as StreamProps}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duration * props.fps)), fps: props.fps })} />
  <Composition id="CardsReel" component={CardsReel} width={1080} height={1920} fps={30} durationInFrames={60}
    defaultProps={{ fps: 30, duration: 2, cast: [], words: [], lines: [{ start: 0, end: 2, who: 'cube', faces: {} }], amp: [], cards: [] } as CardsProps} calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duration * props.fps)), fps: props.fps })} />
  <Composition id="ChatReel" component={ChatReel} width={1080} height={1920} fps={30} durationInFrames={60}
    defaultProps={{ fps: 30, duration: 2, cast: [], words: [], lines: [{ start: 0, end: 2, who: 'cube', faces: {} }], amp: [], channel: 'ai-news', msgs: [] } as ChatProps} calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duration * props.fps)), fps: props.fps })} />
  <Composition id="DepAvatar" component={DepAvatar} width={800} height={800} fps={30} durationInFrames={1} defaultProps={{ variant: 'duo' } as DepAvatarProps} />
  <Composition id="DepBanner" component={DepBanner} width={2560} height={1440} fps={30} durationInFrames={1} />
  <Composition id="AirDropBanner" component={AirDropBanner} width={2560} height={1440} fps={30} durationInFrames={1} />
  </>
);
