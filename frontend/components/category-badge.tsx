import { CATEGORY_COLORS, CATEGORY_LABELS, type Category } from "@/lib/types";

// Hand-rolled badge so we can apply per-category colors without fighting
// Tailwind's purge. We use inline styles for color only.
export function CategoryBadge({
  category,
  muted = false,
}: {
  category: Category;
  muted?: boolean;
}) {
  const color = CATEGORY_COLORS[category];
  const label = CATEGORY_LABELS[category];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: muted ? `${color}22` : `${color}33`,
        color: color,
        border: `1px solid ${color}44`,
      }}
    >
      {label}
    </span>
  );
}
