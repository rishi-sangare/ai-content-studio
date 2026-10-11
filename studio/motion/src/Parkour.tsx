import React, { useLayoutEffect, useMemo } from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { ThreeCanvas } from '@remotion/three';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

// Original voxel parkour run (our own blocks + pixel textures drawn here — no game assets): a first-person runner sprints
// along floating block platforms, jumping the gaps, over a far-below sea with floating islands and flat clouds.
// Deterministic: everything comes from `seed` and the frame number.

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Tex = 'grass_top' | 'grass_side' | 'dirt' | 'stone' | 'planks' | 'leaves' | 'log' | 'sand' | 'gold' | 'brick';

function pixelTexture(kind: Tex, seed: number): THREE.Texture {
  const r = rng(seed);
  const c = document.createElement('canvas');
  c.width = c.height = 16;
  const g = c.getContext('2d')!;
  const px = (x: number, y: number, rgb: [number, number, number], j = 18) => {
    const d = (r() - 0.5) * j;
    g.fillStyle = `rgb(${rgb[0] + d},${rgb[1] + d},${rgb[2] + d})`;
    g.fillRect(x, y, 1, 1);
  };
  for (let y = 0; y < 16; y++)
    for (let x = 0; x < 16; x++) {
      switch (kind) {
        case 'grass_top': px(x, y, [96, 168, 64], 34); break;
        case 'dirt': px(x, y, [134, 96, 67], 30); break;
        case 'grass_side': px(x, y, y < 3 + (r() < 0.4 ? 1 : 0) ? [96, 168, 64] : [134, 96, 67], 30); break;
        case 'stone': px(x, y, [128, 128, 128], 34); break;
        case 'sand': px(x, y, [219, 207, 163], 18); break;
        case 'gold': px(x, y, [246, 208, 60], 40); break;
        case 'leaves': px(x, y, r() < 0.15 ? [40, 80, 30] : [62, 128, 48], 30); break;
        case 'log': px(x, y, x % 4 === 0 ? [80, 60, 36] : [104, 80, 50], 16); break;
        case 'planks': px(x, y, y % 4 === 3 || (x === ((y >> 2) % 2 ? 4 : 12) ) ? [120, 90, 52] : [168, 132, 82], 14); break;
        case 'brick': px(x, y, y % 4 === 3 || x === ((y >> 2) % 2 ? 0 : 8) ? [190, 190, 180] : [150, 74, 60], 16); break;
      }
    }
  const t = new THREE.CanvasTexture(c);
  t.magFilter = THREE.NearestFilter;
  t.minFilter = THREE.NearestFilter;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

type Block = { x: number; y: number; z: number; k: 'grass' | 'stone' | 'planks' | 'leaves' | 'log' | 'sand' | 'gold' | 'brick' };
type Plat = { x: number; y: number; z0: number; z1: number };   // runs from z0 (near) to z1 (far), z decreasing

function world(seed: number, length: number) {
  const r = rng(seed);
  const blocks: Block[] = [];
  const plats: Plat[] = [];
  let z = 2, x = 0, y = 0, i = 0;
  const kinds: Block['k'][] = ['grass', 'grass', 'stone', 'planks', 'sand', 'brick', 'gold'];
  while (z > -length - 30) {
    const len = i === 0 ? 6 : 1 + Math.floor(r() * 3);
    const k = i === 0 ? 'grass' : kinds[Math.floor(r() * kinds.length)];
    plats.push({ x, y, z0: z, z1: z - len + 1 });
    for (let j = 0; j < len; j++) {
      blocks.push({ x, y, z: z - j, k });
      if (k === 'grass') blocks.push({ x, y: y - 1, z: z - j, k: 'stone' });
    }
    const gap = 2 + Math.floor(r() * 2);          // 1–2 empty blocks between platforms
    z -= len - 1 + gap;
    const dy = r();
    y += dy < 0.3 ? 1 : dy < 0.55 ? -1 : 0;
    y = Math.max(-3, Math.min(4, y));
    const dx = r();
    x += dx < 0.2 ? -1 : dx < 0.4 ? 1 : 0;
    x = Math.max(-2, Math.min(2, x));
    i++;
  }
  // floating islands with trees, both sides of the course
  for (let n = 0; n < 70; n++) {
    const side = r() < 0.5 ? -1 : 1;
    const ix = side * (10 + r() * 28), iz = 10 - r() * (length + 40), iy = -14 + r() * 12;
    const w = 2 + Math.floor(r() * 3);
    for (let a = -w; a <= w; a++)
      for (let b = -w; b <= w; b++) {
        if (a * a + b * b > w * w + 1) continue;
        const X = Math.round(ix + a), Z = Math.round(iz + b), Y = Math.round(iy);
        blocks.push({ x: X, y: Y, z: Z, k: 'grass' });
        const depth = 1 + Math.floor((w * w - a * a - b * b) / 3);
        for (let d = 1; d <= depth; d++) blocks.push({ x: X, y: Y - d, z: Z, k: d === 1 ? 'grass' : 'stone' });
      }
    if (r() < 0.75) {
      const X = Math.round(ix), Z = Math.round(iz), Y = Math.round(iy);
      const h = 3 + Math.floor(r() * 2);
      for (let d = 1; d <= h; d++) blocks.push({ x: X, y: Y + d, z: Z, k: 'log' });
      for (let a = -2; a <= 2; a++) for (let b = -2; b <= 2; b++) for (let c = 0; c < 2; c++)
        if (Math.abs(a) + Math.abs(b) < 4) blocks.push({ x: X + a, y: Y + h + c, z: Z + b, k: 'leaves' });
      blocks.push({ x: X, y: Y + h + 2, z: Z, k: 'leaves' });
    }
  }
  return { blocks, plats };
}

const EYE = 0.5 + 1.62;

function camAt(plats: Plat[], d: number) {
  // d = distance run along -z. Position on a platform or in the jump arc between two.
  const z = 2 - d;
  for (let i = 0; i < plats.length; i++) {
    const p = plats[i];
    if (z <= p.z0 + 0.5 && z >= p.z1 - 0.5) return { x: p.x, y: p.y + EYE, z, air: 0 };
    const q = plats[i + 1];
    if (q && z < p.z1 - 0.5 && z > q.z0 + 0.5) {
      const u = (p.z1 - 0.5 - z) / (p.z1 - 0.5 - (q.z0 + 0.5));
      const s = u * u * (3 - 2 * u);
      const y = p.y + EYE + (q.y - p.y) * u + 4 * 1.25 * u * (1 - u);
      return { x: p.x + (q.x - p.x) * s, y, z, air: 1 };
    }
  }
  return { x: 0, y: EYE, z, air: 0 };
}

const SPEED = 5.2; // blocks per second (sprint)

const Rig: React.FC<{ plats: Plat[] }> = ({ plats }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { camera } = useThree();
  useLayoutEffect(() => {
    const t = frame / fps;
    const d = t * SPEED;
    const c = camAt(plats, d);
    const ahead = camAt(plats, d + 4.5);
    const bob = c.air ? 0 : Math.sin(t * Math.PI * 2 * 2.6) * 0.055;
    const sway = c.air ? 0 : Math.sin(t * Math.PI * 2.6) * 0.03;
    camera.position.set(c.x + sway, c.y + bob, c.z);
    camera.lookAt(ahead.x * 0.7 + c.x * 0.3, Math.min(ahead.y, c.y) - 1.25, ahead.z);
    (camera as THREE.PerspectiveCamera).updateProjectionMatrix();
  }, [frame, fps, camera, plats]);
  return null;
};

const Blocks: React.FC<{ blocks: Block[]; seed: number }> = ({ blocks, seed }) => {
  const meshes = useMemo(() => {
    const geo = new THREE.BoxGeometry(1, 1, 1);
    const tex = (k: Tex, s: number) => new THREE.MeshLambertMaterial({ map: pixelTexture(k, seed + s) });
    const side = tex('grass_side', 1), top = tex('grass_top', 2), dirt = tex('dirt', 3);
    const mats: Record<Block['k'], THREE.Material | THREE.Material[]> = {
      grass: [side, side, top, dirt, side, side],
      stone: tex('stone', 4), planks: tex('planks', 5), leaves: tex('leaves', 6), log: tex('log', 7),
      sand: tex('sand', 8), gold: tex('gold', 9), brick: tex('brick', 10),
    };
    const m = new THREE.Matrix4();
    return (Object.keys(mats) as Block['k'][]).map((k) => {
      const list = blocks.filter((b) => b.k === k);
      const mesh = new THREE.InstancedMesh(geo, mats[k], Math.max(1, list.length));
      list.forEach((b, i) => { m.makeTranslation(b.x, b.y, b.z); mesh.setMatrixAt(i, m); });
      mesh.count = list.length;
      mesh.instanceMatrix.needsUpdate = true;
      return mesh;
    });
  }, [blocks, seed]);
  return <>{meshes.map((m, i) => <primitive key={i} object={m} />)}</>;
};

const Clouds: React.FC<{ seed: number; length: number }> = ({ seed, length }) => {
  const list = useMemo(() => {
    const r = rng(seed + 99);
    return Array.from({ length: 40 }, () => ({ x: (r() - 0.5) * 120, z: 20 - r() * (length + 80), w: 6 + r() * 14, d: 4 + r() * 10 }));
  }, [seed, length]);
  return (
    <>
      {list.map((c, i) => (
        <mesh key={i} position={[c.x, 26, c.z]}>
          <boxGeometry args={[c.w, 1.2, c.d]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.92} />
        </mesh>
      ))}
    </>
  );
};

export type ParkourProps = { width: number; height: number; seed?: number; duration: number };

export const Parkour: React.FC<ParkourProps> = ({ width, height, seed = 7, duration }) => {
  const length = duration * SPEED + 10;
  const { blocks, plats } = useMemo(() => world(seed, length), [seed, length]);
  return (
    <ThreeCanvas width={width} height={height} camera={{ fov: 78, near: 0.1, far: 220, position: [0, EYE, 2] }}
      gl={{ antialias: true }} style={{ background: '#87c6ff' }}>
      <color attach="background" args={['#8fcbff']} />
      <fog attach="fog" args={['#cfe8ff', 30, 140]} />
      <hemisphereLight args={['#ffffff', '#5a7a5a', 1.6]} />
      <directionalLight position={[30, 60, 20]} intensity={1.9} />
      <Rig plats={plats} />
      <Blocks blocks={blocks} seed={seed} />
      <Clouds seed={seed} length={length} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -24, -length / 2]}>
        <planeGeometry args={[400, length + 300]} />
        <meshLambertMaterial color="#3d7fd6" />
      </mesh>
    </ThreeCanvas>
  );
};
