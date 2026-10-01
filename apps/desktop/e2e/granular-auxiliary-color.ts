/** WCAG relative luminance for computed CSS hex colors, including #rgb. */
export function contrastRatio(foreground: string, background: string): number {
  function luminance(value: string): number {
    const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
    if (!match) throw new Error(`Unsupported CSS color: ${value}`);
    const short = match[1]!;
    const full = short.length === 3 ? [...short].map(channel => channel + channel).join('') : short;
    const rgb = [0, 2, 4].map(index => parseInt(full.slice(index, index + 2), 16) / 255)
      .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
    return rgb[0]! * 0.2126 + rgb[1]! * 0.7152 + rgb[2]! * 0.0722;
  }
  const first = luminance(foreground), second = luminance(background);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}
