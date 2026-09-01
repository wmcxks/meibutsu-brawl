/**
 * levels.ts
 * Level definitions for the H5 port. Pure data — no Phaser / DOM code.
 *
 * Level 1: tutorial (新手教学) — one centered 3x3x3 stack, 3 icon types,
 *          generous spacing so the player learns pick -> tray -> match.
 * Level 2: brutal (终极挑战) — faithful port of the original level 2:
 *          237 cards, 12 icon types, 10 regions (diagonal/block/ring/cover).
 */

import type {
  LevelConfig,
  RegionConfig,
  LayerConfig,
  CardPos,
} from "../types/game";

/** cols x rows grid of card positions, optionally shifted down by rows. */
const grid = (cols: number, rows: number, rowOffset = 0): CardPos[] =>
  Array.from({ length: cols * rows }, (_, i) => ({
    col: i % cols,
    row: Math.floor(i / cols) + rowOffset,
  }));

/** 8-layer single-card diagonal stack (original regions 1 & 2). */
function diagonalStack(regionX: number): RegionConfig {
  const layers: LayerConfig[] = [];
  for (let i = 0; i < 8; i++) {
    layers.push({
      layer: i,
      gapRatio: 0.1,
      offsetCol: i * 0.1,
      cards: [{ col: 0, row: 0 }],
    });
  }
  return { x: regionX, y: 0.05, layers };
}

/** 16-layer 2x2 / centered-1 alternating blocks (original regions 3.1 & 3.2). */
function blockStack(regionX: number): RegionConfig {
  const layers: LayerConfig[] = [];
  for (let i = 0; i < 16; i++) {
    if (i % 2 === 0) {
      layers.push({ layer: i, gapRatio: 0.1, cards: grid(2, 2) });
    } else {
      layers.push({
        layer: i,
        gapRatio: 0.1,
        offsetCol: 0.5,
        offsetRow: 0.5,
        cards: [{ col: 0, row: 0 }],
      });
    }
  }
  return { x: regionX, y: 0.22, layers };
}

/** Ring staircase: 24 layers circling the 4 cardinal directions (region 3.3). */
const RING_DIRECTIONS = [
  { offsetCol: 1, offsetRow: 0.5 },
  { offsetCol: 0.5, offsetRow: 1 },
  { offsetCol: 0, offsetRow: 0.5 },
  { offsetCol: 0.5, offsetRow: 0 },
];

function ringStack(): RegionConfig {
  const layers: LayerConfig[] = [];
  for (let i = 0; i < 24; i++) {
    const d = RING_DIRECTIONS[i % 4];
    layers.push({
      layer: i,
      gapRatio: 0.1,
      offsetCol: d.offsetCol,
      offsetRow: d.offsetRow,
      cards: [{ col: 0, row: 0 }],
    });
  }
  return { x: 0.345, y: 0.52, layers };
}

/** 16-layer vertical 2 / centered-1 alternating stacks (regions 3.4 & 3.5). */
function verticalStack(regionX: number): RegionConfig {
  const layers: LayerConfig[] = [];
  for (let i = 0; i < 16; i++) {
    if (i % 2 === 0) {
      layers.push({
        layer: i,
        gapRatio: 0.1,
        cards: [
          { col: 0, row: 0 },
          { col: 0, row: 1 },
        ],
      });
    } else {
      layers.push({
        layer: i,
        gapRatio: 0.1,
        offsetCol: 0,
        offsetRow: 0.5,
        cards: [{ col: 0, row: 0 }],
      });
    }
  }
  return { x: regionX, y: 0.52, layers };
}

/** 6-layer corner stack, alternating offset (regions 4 & 5, mirrored by x). */
function cornerStack(regionX: number): RegionConfig {
  const layers: LayerConfig[] = [];
  for (let i = 0; i < 6; i++) {
    const offset = i % 2 === 0 ? 0 : regionX < 0.5 ? 0.5 : -0.5;
    layers.push({
      layer: i,
      gapRatio: 0.1,
      offsetCol: offset,
      cards: [{ col: 0, row: 0 }],
    });
  }
  return { x: regionX, y: 0.82, layers };
}

/** Top cover (region 6): 6x6 sheet + centered 3x3 + 6x2 rows 3-4. */
const topCover: RegionConfig = {
  x: 0.06,
  y: 0.17,
  layers: [
    { layer: 50, gapRatio: 0.1, cards: grid(6, 6) },
    {
      layer: 51,
      gapRatio: 0.1,
      offsetCol: 1.5,
      offsetRow: 1.5,
      cards: grid(3, 3).map((p) => ({
        col: p.col * 2 - 1,
        row: p.row * 2 - 1,
      })),
    },
    { layer: 52, gapRatio: 0.1, cards: [...grid(6, 1, 3), ...grid(6, 1, 4)] },
  ],
};

/** All levels, in play order. */
export const LEVELS: LevelConfig[] = [
  {
    title: "新手教学",
    iconTypes: 3,
    regions: [
      {
        // One centered region: 3 layers of 3x3 with generous gaps (learning layout).
        x: 0.18,
        y: 0.25,
        layers: [
          { layer: 0, gapRatio: 0.8, cards: grid(3, 3) },
          // { layer: 1, gapRatio: 0.8, offsetRow: 0.3, cards: grid(3, 3) },
          // { layer: 2, gapRatio: 0.8, offsetRow: 0.6, cards: grid(3, 3) },
        ],
      },
    ],
  },
  {
    title: "终极挑战",
    iconTypes: 12,
    regions: [
      diagonalStack(0.05), // region 1: left-top diagonal
      diagonalStack(0.81), // region 2: right-top mirror
      blockStack(0.12), // region 3.1: left middle blocks
      blockStack(0.54), // region 3.2: right middle mirror
      ringStack(), // region 3.3: center ring staircase
      verticalStack(0.08), // region 3.4: left of ring
      verticalStack(0.78), // region 3.5: right of ring
      cornerStack(0.05), // region 4: left-bottom corner
      cornerStack(0.81), // region 5: right-bottom corner
      topCover, // region 6: top sheet covering the middle
    ],
  },
];
