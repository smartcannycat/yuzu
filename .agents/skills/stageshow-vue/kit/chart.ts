import type { ChartProps } from './Chart.vue'

export { default as Chart } from './Chart.vue'
export type { ChartProps } from './Chart.vue'

export function chartPoints({
  data,
  kind = 'line',
  width,
  height,
  dot = true,
  max,
}: Pick<ChartProps, 'data' | 'kind' | 'width' | 'height' | 'dot' | 'max'>) {
  const top = max ?? Math.max(...data, 1)
  const pad = kind === 'line' && dot ? 4 : 1
  const h = height - pad * 2
  if (kind === 'bars') {
    const gap = Math.max(2, Math.round(width / data.length / 4))
    const bw = (width - gap * (data.length - 1)) / data.length
    return data.map((v, i) => ({
      x: i * (bw + gap) + bw / 2,
      y: height - Math.max(2, (v / top) * h),
    }))
  }
  return data.map((v, i) => ({
    x: pad + (i / Math.max(1, data.length - 1)) * (width - pad * 2),
    y: pad + h - (v / top) * h,
  }))
}
