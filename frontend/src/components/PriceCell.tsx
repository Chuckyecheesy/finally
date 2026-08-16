"use client";

import { useEffect, useRef, useState } from "react";
import { price as formatPrice } from "@/lib/format";

interface PriceCellProps {
  value: number | null | undefined;
  className?: string;
}

/**
 * Renders a price and washes the cell green/red for ~500ms whenever the value
 * changes. The animated span is remounted with a fresh key on each change,
 * which is what restarts the CSS animation mid-flight.
 */
export function PriceCell({ value, className = "" }: PriceCellProps) {
  const previous = useRef<number | null | undefined>(value);
  const [flash, setFlash] = useState<{ direction: "up" | "down"; tick: number } | null>(null);
  const tick = useRef(0);

  useEffect(() => {
    const before = previous.current;
    previous.current = value;
    if (typeof value !== "number" || typeof before !== "number" || value === before) return;
    tick.current += 1;
    setFlash({ direction: value > before ? "up" : "down", tick: tick.current });
  }, [value]);

  const flashClass = flash ? (flash.direction === "up" ? "flash-up" : "flash-down") : "";

  return (
    <span
      key={flash?.tick ?? 0}
      data-testid="price-cell"
      className={`tnum inline-block px-1 text-right ${flashClass} ${className}`}
    >
      {formatPrice(value)}
    </span>
  );
}
