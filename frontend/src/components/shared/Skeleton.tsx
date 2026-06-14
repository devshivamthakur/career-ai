interface SkeletonProps {
  className?: string;
  count?: number;
  height?: string;
}

export function Skeleton({ className = '', count = 1, height = '16px' }: SkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`skeleton-shimmer rounded-md ${className}`}
          style={{ height, marginBottom: count > 1 ? '8px' : undefined }}
        />
      ))}
    </>
  );
}


