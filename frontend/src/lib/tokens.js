// Design tokens for canvas code. Canvas can't read CSS variables, so components
// resolve them here: `token` returns the raw value, `toRgb` converts any CSS colour
// (hex, oklch(), color-mix()) to sRGB bytes through a 1px canvas. Tokens are always
// defined in index.css, so there are no hard-coded fallbacks to drift out of sync.

export const token = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

let probe = null
export function toRgb(color) {
  if (!probe) {
    const c = document.createElement('canvas')
    c.width = c.height = 1
    probe = c.getContext('2d', { willReadFrequently: true })
  }
  probe.clearRect(0, 0, 1, 1)
  probe.fillStyle = color
  probe.fillRect(0, 0, 1, 1)
  const [r, g, b] = probe.getImageData(0, 0, 1, 1).data
  return [r, g, b]
}

export const rgbToken = name => toRgb(token(name))
