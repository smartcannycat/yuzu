import { CAPY_BLINK, CAPY_EAR_TWITCH, CAPY_READ_X, CAPY_READ_Y } from './capyPoses'
import type { MascotEyeFrame } from './MascotHeadSvg.vue'
import { bell, clamp01, loop, mix, track, wave, type ChannelsController } from './motion'
import { MASCOT_COLORS, MASCOT_EYES_X, MASCOT_EYE_Y } from './palette'

export interface CapyPawPose {
  x: number
  y: number
  w: number
  h: number
  rot: number
  fill: string
}

export interface CapyFramePose {
  body: { x: number; y: number; w: number; h: number; rx: number }
  headTf: string
  earL: number
  earR: number
  open: number
  eyes: MascotEyeFrame[]
  closedOp: number
  cheekY: number
  mouth: string
  shadowW: number
  pawL: CapyPawPose
  pawR: CapyPawPose
  sheetOp: number
  sheetY: number
  scanY: number
  loupeOp: number
  loupeTf: string
  flagOp: number
  flagTf: string
  yuzuRock: number
  cautionOp: number
  cautionTf: string
  cautionPulse: number
  sigOp: number
  sigTf: string
  redRings: Array<{ op: number; offset: number }>
  questions: Array<{ op: number; tf: string; color: string }>
  zzz: Array<{ op: number; color: string; d: string }>
}

export function evaluateCapyFrame(
  ch: ChannelsController,
  T: number,
  t0: number,
  isActive: boolean,
  isCompact: boolean,
): CapyFramePose {
  const t = isActive ? T - t0 : 0
  const c = (k: string, dt = 0) => ch.at(k, T - dt)

  const wS = c('wSleep')
  const wP = c('wPeek')
  const wT = c('wThink')
  const wG = c('wGreen')
  const wY = c('wYellow')
  const wR = c('wRed')
  const wE = c('wError')

  const idleScale = isCompact ? 0.55 : 1

  const breath = (tt: number) =>
    (wS * wave(tt, 4200) +
      wP * 0.7 * wave(tt, 2800) +
      wT * 0.65 * wave(tt, 1900) +
      (wG + wY + wR + wE) * 0.55 * wave(tt, 3400)) *
    idleScale
  const b = breath(t)
  const bLate = breath(t - 150)

  const sit = c('sit')
  const W0 = mix(126, 114, sit)
  const H0 = mix(56, 61, sit)
  const sy = 1 + 0.026 * b
  const sx = 1 / Math.pow(sy, 0.6)
  const bodyW = W0 * sx
  const bodyH = H0 * sy
  const bodyBottom = 150

  const redArrived = ch.raw.signal?.to === 1 ? ch.sinceArrived('signal', T) : -1
  const redShake =
    redArrived >= 0 && redArrived < 850 && isActive
      ? 4.2 * bell(redArrived / 850) * wave(redArrived, 280)
      : 0

  const tiltIdle = (tt: number) =>
    (wS * 1.4 * wave(tt, 4200, 0.15) +
      wT * 2.2 * wave(tt, 3200, 0.25) +
      wG * 2.0 * wave(tt, 2800, 0.1) +
      wY * 1.4 * wave(tt, 3600, 0.2) +
      wE * 1.6 * wave(tt, 3800, 0.3)) *
    idleScale

  const tilt = c('tilt') + tiltIdle(t)
  const tiltLate = c('tilt', 110) + tiltIdle(t - 110)
  const ft = tiltLate - tilt

  const hx = c('headX') + redShake + wT * 1.2 * wave(t, 3200, 0.1) * idleScale
  const hy = c('headY') - H0 * 0.026 * bLate * 0.85

  const ear = c('ear')
  const earWaveAmp = (wT * 0.9 + wS * 0.35 + (wG + wY + wR + wE) * 0.5) * idleScale
  const twitch = wS * track(loop(t, 5600) * 5600, CAPY_EAR_TWITCH)
  const earL = -(ear + 2.8 * earWaveAmp * wave(t, 3100)) + 0.6 * ft
  const earR = ear + 2.8 * earWaveAmp * wave(t, 2700, 0.37) + twitch + 0.6 * ft

  const thinkCycle = loop(t, 6400)
  const thinkZoom = wT * bell(clamp01((thinkCycle - 0.52) / 0.44))

  const blink = track(loop(t, 3800) * 3800, CAPY_BLINK)
  const awakeWeight = clamp01(1 - wS - wG)
  const open = clamp01(c('eyeOpen') * mix(1, blink, awakeWeight))

  const readT = loop(t, 3600) * 3600
  const lookX = c('lookX') + wT * track(readT, CAPY_READ_X) + redShake * 0.45
  const lookY = c('lookY') + wT * track(readT, CAPY_READ_Y)

  const happy = c('happy')
  const lidFlat = c('lidFlat')
  const lidRightExtra = c('lidRightExtra') + 0.38 * thinkZoom
  const sadTilt = c('sadTilt')

  const baseLidClose = 32 * 0.9 * (1 - open)
  const lowH = 32 * 0.26 * (1 - open) + 1.2 + 5 * thinkZoom * 0.5
  const closedOp = clamp01((0.28 - open) / 0.28)
  const closedY = MASCOT_EYE_Y + 9 - 4 * happy
  const closedCurve = mix(4, -9, happy)

  const eyes: MascotEyeFrame[] = MASCOT_EYES_X.map((cx, idx) => {
    const extraTop = idx === 1 ? 30 * lidRightExtra : 0
    const flatTop = 30 * lidFlat
    const lidH = Math.min(34, Math.max(baseLidClose, flatTop, extraTop) + 2)
    const lidAngle = sadTilt * (idx === 0 ? -14 : 14)
    return {
      cx,
      pupilX: cx - 5 + lookX,
      pupilY: MASCOT_EYE_Y - 10 + lookY,
      lidH,
      lowY: MASCOT_EYE_Y + 15 - lowH,
      lowH,
      lidTf: `rotate(${lidAngle} ${cx} ${MASCOT_EYE_Y - 4})`,
      closed: `M ${cx - 8} ${closedY} Q ${cx} ${closedY + closedCurve} ${cx + 8} ${closedY}`,
    }
  })

  const mo = c('mouthOpen')
  const fr = c('frown')
  const mw = 6.2 - 1.6 * mo
  const my = 23 + 1.5 * fr
  const arch = mix(4.2, -4.8, fr)
  const mouth =
    `M ${-mw} ${my} ` +
    `Q 0 ${my + arch + 4.5 * mo} ${mw} ${my} ` +
    `Q 0 ${my + arch - 3.2 * mo} ${-mw} ${my} Z`

  const pawLX = c('pawLX') - wE * 2 * wave(t, 2800) * idleScale
  const pawLY = c('pawLY') + wT * 1.2 * wave(t, 1900)
  const pawRX = c('pawRX') + wE * 2 * wave(t, 2800, 0.5) * idleScale
  const pawRY =
    c('pawRY') + wT * (-4 * thinkZoom + 2.5 * wave(t, 3200)) + wG * 1.5 * wave(t, 2800) * idleScale
  const pawChin = c('pawChin')
  const shrug = c('shrug')

  const sheetVal = c('sheet')
  const sheetY = (1 - sheetVal) * 28 + 1.8 * wave(t, 2600)
  const scanY = 105 + ((wave(t, 2200) + 1) / 2) * 28

  const loupeVal = c('loupe')
  const loupeScale = 0.88 + 0.12 * loupeVal + 0.08 * thinkZoom
  const loupeRot = -12 + 8 * wave(t, 3200) + 6 * thinkZoom + 1.1 * ft
  const loupeTf =
    `translate(${pawRX} ${pawRY}) ` +
    `rotate(${loupeRot}) scale(${loupeScale}) translate(${-pawRX} ${-pawRY})`

  const flagVal = c('flag')
  const flagArrived = ch.raw.flag?.to === 1 ? ch.sinceArrived('flag', T) : -1
  const flagEntranceWave =
    flagArrived >= 0 && flagArrived < 1200 && isActive
      ? 9.5 * bell(flagArrived / 1200) * wave(flagArrived, 380)
      : 0
  const flagRot =
    14 +
    (1 - flagVal) * 22 +
    flagEntranceWave +
    2.4 * wG * wave(t, 2800, 0.15) * idleScale +
    1.3 * ft
  const flagTf = `translate(${pawRX} ${pawRY + 4}) rotate(${flagRot}) translate(0 ${(1 - flagVal) * 18})`
  const yuzuRock = 1.6 * ft + 0.5 * flagEntranceWave

  const cautionVal = c('caution')
  const cautionArrived = ch.raw.caution?.to === 1 ? ch.sinceArrived('caution', T) : -1
  const cautionEntrance =
    cautionArrived >= 0 && cautionArrived < 1000 && isActive
      ? 6 * bell(cautionArrived / 1000) * wave(cautionArrived, 340)
      : 0
  const cautionRot =
    8 + (1 - cautionVal) * 18 + cautionEntrance + 1.8 * wY * wave(t, 3400) * idleScale + 1.1 * ft
  const cautionTf = `translate(${pawRX + 2} ${pawRY + 4}) rotate(${cautionRot}) translate(0 ${(1 - cautionVal) * 18})`
  const cautionPulse = bell(loop(t, 1600)) * cautionVal * wY

  const sigVal = c('signal')
  const sigRot = 1.2 * wR * wave(t, 3200) * idleScale + 0.8 * ft
  const sigTf = `translate(${pawRX + 4} ${pawRY + 4}) rotate(${sigRot}) translate(0 ${(1 - sigVal) * 22})`
  const redRings = [0, 1].map((i) => {
    const q = loop(t, 1250, i * 0.5)
    return { op: bell(q) * sigVal * wR, offset: 4 * q }
  })

  const questions = [0, 1].map((i) => {
    const q = loop(t, 3200, i * 0.5)
    const qx = 148 + i * 14 + 3 * wave(t, 1800, i * 0.4)
    const qy = 66 - 26 * q
    const qs = 0.85 + 0.25 * q
    return {
      op: bell(q) * shrug * wE,
      tf: `translate(${qx} ${qy}) scale(${qs}) rotate(${8 * wave(t, 2000, i)})`,
      color: i === 0 ? MASCOT_COLORS.scanOrange : MASCOT_COLORS.zzz[1],
    }
  })

  const zzz = [0, 1, 2].map((i) => {
    const q = loop(t, 3600, i / 3)
    const zs = 3.5 + 3.5 * q
    const zx = 142 + 16 * q + 2 * wave(t, 1700, i * 0.3)
    const zy = 68 - 36 * q
    return {
      op: bell(q) * wS,
      color: MASCOT_COLORS.zzz[i] ?? MASCOT_COLORS.zzz[0],
      d: `M ${zx - zs} ${zy - zs} L ${zx + zs} ${zy - zs} L ${zx - zs} ${zy + zs} L ${zx + zs} ${zy + zs}`,
    }
  })

  return {
    body: {
      x: hx - bodyW / 2,
      y: bodyBottom - bodyH,
      w: bodyW,
      h: bodyH,
      rx: Math.min(bodyW, bodyH) * 0.46,
    },
    headTf: `translate(${hx} ${hy}) rotate(${tilt} 0 30)`,
    earL,
    earR,
    open,
    eyes,
    closedOp,
    cheekY: 6 - 2 * happy,
    mouth,
    shadowW: c('shadowW') * (1 + 0.015 * b),
    pawL: {
      x: pawLX,
      y: pawLY,
      w: 22 + 3 * shrug,
      h: 14 - 1 * shrug,
      rot: -18 * shrug,
      fill: pawChin > 0.4 ? MASCOT_COLORS.muzzleShade : MASCOT_COLORS.muzzle,
    },
    pawR: {
      x: pawRX,
      y: pawRY,
      w: 22 + 3 * shrug,
      h: 14 - 1 * shrug,
      rot: 18 * shrug,
      fill: MASCOT_COLORS.muzzle,
    },
    sheetOp: clamp01(sheetVal * 2.2),
    sheetY,
    scanY,
    loupeOp: clamp01(loupeVal * 2.2),
    loupeTf,
    flagOp: clamp01(flagVal * 2.5),
    flagTf,
    yuzuRock,
    cautionOp: clamp01(cautionVal * 2.5),
    cautionTf,
    cautionPulse,
    sigOp: clamp01(sigVal * 2.5),
    sigTf,
    redRings,
    questions,
    zzz,
  }
}
