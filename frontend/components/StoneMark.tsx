export default function StoneMark({ size=32 }: { size?: number }) {
    return (
        <div
            className="flex shrink-0 items-center justify-center rounded-md font-display font-bold text-white shadow-sm"
            style={{
                width:size,
                height:size,
                fontSize:size * 0.8,
                background: "linear-gradient(135deg, #2AA7DE 0%, #1B355E 100%)"
            }}
        >
            S
        </div>
    );
}