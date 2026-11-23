import { logo_aspect, tile } from "@/lib/logoTile";

export default function StoneMark({ size = 32 }: {size?: number}) {
    const imgW = size / tile.w;
    const imgH = imgW / logo_aspect;
    return(
        <div
            data-nav-mark
            className="relative shrink-0 overflow-hidden"
            style={{ width: size, height: size }}
            aria-label="Stone Commercial"
            role="img"
        >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
                src="/logo.png"
                alt=""
                draggable={false}
                style={{
                    position:"absolute",
                    maxWidth: "none",
                    width: imgW,
                    height: imgH,
                    left: -tile.left * imgW,
                    top: -tile.top * imgH
                }}
            />
        </div>
    );
}