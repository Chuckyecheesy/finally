interface SparklineProps {
  points: number[];
  width?: number;
  height?: number;
}

/**
 * Hand-rolled inline SVG rather than a chart component: one of these renders
 * per watchlist row and redraws twice a second, so it stays allocation-light.
 */
export function Sparkline({ points, width = 56, height = 18 }: SparklineProps) {
  if (points.length < 2) {
    return (
      <svg width={width} height={height} aria-hidden className="opacity-40">
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeDasharray="2 3"
          className="text-terminal-faint"
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const pad = 1.5;
  const usable = height - pad * 2;

  const path = points
    .map((value, index) => `${(index * step).toFixed(2)},${(pad + (1 - (value - min) / span) * usable).toFixed(2)}`)
    .join(" ");

  const rising = points[points.length - 1] >= points[0];

  return (
    <svg width={width} height={height} aria-hidden className={rising ? "text-up" : "text-down"}>
      <polyline
        points={path}
        fill="none"
        stroke="currentColor"
        strokeWidth={1}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
