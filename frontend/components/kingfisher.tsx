import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  size?: number;
  title?: string;
};

export function Kingfisher({ className, size = 28, title = "Sente" }: Props) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={cn("shrink-0", className)}
    >
      <title>{title}</title>
      {/* Body — deep green, rounded back, low-slung */}
      <path
        d="M9 38 C 11 27, 22 19, 34 19 C 41 19, 47 22, 51 27 L 58 25 L 53 31 C 55 35, 55 39, 53 43 L 48 47 C 44 51, 38 53, 32 53 L 28 53 L 26 58 L 24 53 L 18 53 L 16 58 L 14 53 C 11 50, 9 45, 9 38 Z"
        fill="hsl(var(--leaf))"
      />
      {/* Wing — slightly darker overlap */}
      <path
        d="M22 32 C 28 28, 36 28, 44 31 C 41 38, 33 42, 24 41 C 22 38, 21 35, 22 32 Z"
        fill="hsl(var(--ink))"
        opacity="0.35"
      />
      {/* Breast patch — kingfisher red */}
      <path
        d="M21 39 C 25 37, 32 37, 37 40 C 36 46, 31 49, 25 49 C 22 47, 20 43, 21 39 Z"
        fill="hsl(var(--kingfisher))"
      />
      {/* Beak — small point */}
      <path d="M58 25 L 64 23 L 58 28 Z" fill="hsl(var(--ink))" />
      {/* Eye */}
      <circle cx="48" cy="27" r="1.4" fill="hsl(var(--paper))" />
      <circle cx="48" cy="27" r="0.7" fill="hsl(var(--ink))" />
    </svg>
  );
}
