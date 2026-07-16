interface StarRatingProps {
  value: number;
  onChange?: (stars: number) => void;
  size?: number;
}

/** Read-only when onChange is omitted; otherwise an interactive 1-5 picker. */
export function StarRating({ value, onChange, size = 16 }: StarRatingProps) {
  const interactive = !!onChange;
  return (
    <span
      role={interactive ? "radiogroup" : undefined}
      aria-label={interactive ? "評価を選択" : `評価 ${value} / 5`}
      style={{ display: "inline-flex", gap: 2, fontSize: size, lineHeight: 1 }}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <span
          key={n}
          role={interactive ? "radio" : undefined}
          aria-checked={interactive ? n === value : undefined}
          onClick={interactive ? () => onChange!(n) : undefined}
          style={{
            color: n <= value ? "var(--warning)" : "var(--border)",
            cursor: interactive ? "pointer" : "default",
          }}
        >
          ★
        </span>
      ))}
    </span>
  );
}
