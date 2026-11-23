export const logo_aspect = 2147 / 748

export const tile = {
    left: 0.02492,
    top: 0.06016,
    w: 0.2308,
    h: 0.66
};

export function tileInset(): string {
    const m = 0.002;
    const top = (tile.top - m) * 100;
    const bottom = (1 - tile.top - tile.h - m) * 100;
    const left = (tile.left - m) * 100;
    const right = (1 - tile.left - tile.w - m) * 100;
    return `inset(${top}% ${right}% ${bottom}% ${left}%)`;
}