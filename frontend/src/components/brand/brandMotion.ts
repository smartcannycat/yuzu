import type { MascotEyeFrame } from '@/components/mascot/MascotHeadSvg.vue'
import {
  EASE_IN_OUT,
  bell,
  clamp01,
  loop,
  mix,
  track,
  wave,
  type KeyFrame,
} from '@/components/mascot/motion'
import { MASCOT_COLORS, MASCOT_EYES_X, MASCOT_EYE_Y } from '@/components/mascot/palette'

export const BRAND_BOOP_DURATION = 1150

const BLINK: KeyFrame[] = [
  [0, 1],
  [2800, 1],
  [2900, 0],
  [2950, 0],
  [3120, 1, 'out'],
  [4200, 1],
]

const EAR_TWITCH: KeyFrame[] = [
  [0, 0],
  [4100, 0],
  [4210, -13],
  [4330, 0],
  [4440, -8, 'out'],
  [4600, 0],
  [5800, 0],
]

const GLANCE_X: KeyFrame[] = [
  [0, 0],
  [2400, 0],
  [2750, 2.2, 'out'],
  [3900, 2.2],
  [4300, 0, 'io'],
  [7200, 0],
]

const BOOP_HEAD_Y: KeyFrame[] = [
  [0, 0],
  [120, 2.8, 'io'],
  [340, -7.2, 'out'],
  [580, 1.2, 'in'],
  [820, -0.8, 'out'],
  [1150, 0, 'io'],
]

const BOOP_YUZU_Y: KeyFrame[] = [
  [0, 0],
  [140, 1.5, 'io'],
  [390, -13.5, 'out'],
  [640, 1.6, 'in'],
  [840, -2.4, 'out'],
  [1150, 0, 'io'],
]

export interface BrandLogoSpark {
  op: number
  tf: string
  color: string
}

export interface BrandLogoFrame {
  body: { x: number; y: number; w: number; h: number; rx: number }
  headTf: string
  earL: number
  earR: number
  open: number
  closedOp: number
  eyes: MascotEyeFrame[]
  cheekY: number
  cheekScale: number
  mouthD: string
  yuzuTf: string
  leafTf: string
  pawY: number
  sparks: BrandLogoSpark[]
  letters: string[]
  badgeStyle: { transform: string } | undefined
}

export interface BrandLogoFrameInput {
  T: number
  t0: number
  active: boolean
  hovered: boolean
  hoverChangedAt: number
  boopStart: number
  boopCount: number
}

export function evaluateBrandLogoFrame(input: BrandLogoFrameInput): BrandLogoFrame {
  const { T, t0, active, hovered, hoverChangedAt, boopStart, boopCount } = input
  const t = active ? T - t0 : 0

  const hoverElapsed = clamp01((T - hoverChangedAt) / 220)
  const hoverW = active ? (hovered ? hoverElapsed : 1 - hoverElapsed) : 0

  const boopElapsed = T - boopStart
  const isBooping = active && boopElapsed >= 0 && boopElapsed < BRAND_BOOP_DURATION
  const boopQ = isBooping ? clamp01(boopElapsed / BRAND_BOOP_DURATION) : 0

  const b = active ? wave(t, 4200) : 0
  const bLate = active ? wave(t - 140, 4200) : 0
  const boopHeadDy = isBooping ? track(boopElapsed, BOOP_HEAD_Y) : 0
  const boopSquash = isBooping ? clamp01(1 - Math.abs(boopElapsed - 110) / 110) * 0.08 : 0
  const boopStretch = isBooping ? clamp01(1 - Math.abs(boopElapsed - 340) / 180) * 0.06 : 0

  const sy = 1 + 0.022 * b - boopSquash + boopStretch
  const sx = 1 / Math.pow(sy, 0.6)
  const bodyW = 123 * sx
  const bodyH = 57.25 * sy

  const headY = 87 - 1.2 * bLate - 1.2 * hoverW + boopHeadDy
  const headTilt =
    (active ? 1.3 * wave(t, 3800, 0.15) : 0) +
    hoverW * -2.2 +
    (isBooping ? 5.5 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ * 0.5) : 0)

  const twitch = active ? track(loop(t, 5800) * 5800, EAR_TWITCH) : 0
  const boopEar = isBooping ? -12 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ) : 0
  const earL = -2 - (active ? 1.8 * wave(t, 3100) : 0) - 4 * hoverW + boopEar
  const earR = 2 + (active ? 1.8 * wave(t, 2700, 0.35) : 0) + twitch + 4 * hoverW - boopEar

  const blink = active ? track(loop(t, 4200) * 4200, BLINK) : 1
  const happy = isBooping ? clamp01(Math.sin(boopQ * Math.PI) * 1.65) : 0
  const open = clamp01(blink * (1 - happy * 1.15))
  const closedOp = clamp01((0.32 - open) / 0.32)
  const closedY = MASCOT_EYE_Y + 9 - 4 * happy
  const closedCurve = mix(4, -9, happy)

  const lookX = (active ? track(loop(t, 7200) * 7200, GLANCE_X) : 0) * (1 - hoverW * 0.6)
  const lookY = -0.8 * hoverW

  const eyes: MascotEyeFrame[] = MASCOT_EYES_X.map((cx) => ({
    cx,
    pupilX: cx - 5 + lookX,
    pupilY: MASCOT_EYE_Y - 8.5 + lookY,
    lidH: Math.max(4.2, 28 * (1 - open)),
    lowY: MASCOT_EYE_Y + 11.5,
    lowH: 3.5,
    closed: `M ${cx - 8} ${closedY} Q ${cx} ${closedY + closedCurve} ${cx + 8} ${closedY}`,
  }))

  const isSuperBoop = isBooping && boopCount > 0 && boopCount % 3 === 0
  const yuzuSpin = isSuperBoop
    ? 360 * EASE_IN_OUT(clamp01((boopQ - 0.08) / 0.68))
    : isBooping
      ? 14 * Math.sin(boopQ * Math.PI * 2) * (1 - boopQ)
      : 0
  const yuzuDy = isBooping ? track(boopElapsed, BOOP_YUZU_Y) * (isSuperBoop ? 1.25 : 1) : 0
  const yuzuRot = (active ? 1.8 * wave(t, 3400, 0.25) : 0) + hoverW * 3.5 + yuzuSpin
  const leafRot =
    -22 +
    (active ? 3.5 * wave(t, 2600, 0.1) : 0) +
    hoverW * -5 +
    (isBooping ? -18 * Math.sin(boopQ * Math.PI * 3) * (1 - boopQ) : 0)

  const pawLift = isBooping ? Math.max(0, -boopHeadDy * 0.55) : 0

  const sparks = ([-1, 0, 1] as const).map((dir, i) => {
    const localQ = clamp01((boopQ - 0.12 - i * 0.06) / 0.72)
    const op = isBooping ? bell(localQ) : 0
    const sxPos = dir * (22 + 20 * localQ)
    const syPos = -58 - 18 * localQ - (i === 1 ? 8 * localQ : 0)
    const scale = 0.65 + 0.55 * Math.sin(localQ * Math.PI)
    return {
      op,
      tf: `translate(${sxPos} ${syPos}) scale(${scale})`,
      color: i === 0 ? MASCOT_COLORS.yuzu : i === 1 ? MASCOT_COLORS.scanOrange : MASCOT_COLORS.leaf,
    }
  })

  const letters = [0, 1, 2, 3].map((i) => {
    if (!isBooping) return 'translate(0 0)'
    const lq = clamp01((boopElapsed - i * 55) / 420)
    const dy = -2.4 * Math.sin(lq * Math.PI)
    return `translate(0 ${dy.toFixed(2)})`
  })

  const badgeQ = isBooping ? clamp01((boopElapsed - 210) / 360) : 0
  const badgeScale = 1 + 0.08 * Math.sin(badgeQ * Math.PI)
  const badgeDy = -1.4 * Math.sin(badgeQ * Math.PI)
  const badgeStyle = isBooping
    ? { transform: `translateY(${badgeDy.toFixed(2)}px) scale(${badgeScale.toFixed(3)})` }
    : undefined

  return {
    body: {
      x: 100 - bodyW / 2,
      y: 150 - bodyH,
      w: bodyW,
      h: bodyH,
      rx: Math.min(bodyW, bodyH) * 0.46,
    },
    headTf: `translate(100 ${headY}) rotate(${headTilt} 0 30)`,
    earL,
    earR,
    open,
    closedOp,
    eyes,
    cheekY: 6 - 1.8 * happy,
    cheekScale: 1 + 0.12 * happy,
    mouthD:
      happy > 0.2
        ? 'M -7.4 22.5 Q 0 28.4 7.4 22.5 Q 0 28.4 -7.4 22.5 Z'
        : 'M -6.2 23 Q 0 27.2 6.2 23 Q 0 27.2 -6.2 23 Z',
    yuzuTf: `translate(0 ${-46 + yuzuDy}) rotate(${yuzuRot})`,
    leafTf: `rotate(${leafRot} 1.5 -15)`,
    pawY: 136 - pawLift,
    sparks,
    letters,
    badgeStyle,
  }
}
