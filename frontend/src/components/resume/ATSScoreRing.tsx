import { memo, useEffect, useRef, useState } from 'react';

interface ATSScoreRingProps {
  score: number;
  size?: number;
  animated?: boolean;
}

const CIRCUMFERENCE = 2 * Math.PI * 48; // r=48

function getRingColor(score: number): string {
  if (score >= 75) return '#34D399';
  if (score >= 50) return '#FBBF24';
  return '#F87171';
}

export const ATSScoreRing = memo(function ATSScoreRing({ score, size = 120, animated = true }: ATSScoreRingProps) {
  const circumference = CIRCUMFERENCE;
  const [offset, setOffset] = useState(animated ? circumference : circumference - (score / 100) * circumference);
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!animated || hasAnimated.current) {
      setOffset(circumference - (score / 100) * circumference);
      setDisplayScore(score);
      return;
    }

    // Animate the ring fill
    const startTime = performance.now();
    const duration = 1000; // 1 second

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);

      const currentScore = Math.round(score * eased);
      const currentOffset = circumference - (currentScore / 100) * circumference;

      setDisplayScore(currentScore);
      setOffset(currentOffset);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        hasAnimated.current = true;
      }
    }

    requestAnimationFrame(animate);
  }, [score, animated, circumference]);

  const ringColor = getRingColor(score);

  return (
    <div className="flex flex-col items-center gap-3">
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={48}
          fill="none"
          stroke="var(--border)"
          strokeWidth={8}
        />
        {/* Score ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={48}
          fill="none"
          stroke={ringColor}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: animated ? 'none' : 'stroke-dashoffset 1s ease-out',
          }}
        />
      </svg>

      {/* Center score text */}
      <div
        className="absolute flex flex-col items-center justify-center"
        style={{ width: size, height: size }}
      >
        <span
          className="font-mono font-semibold leading-none"
          style={{
            fontSize: size * 0.25,
            color: ringColor,
          }}
        >
          {displayScore}
        </span>
        <span className="text-xs text-text-secondary font-mono">/ 100</span>
      </div>

      <p className="text-xs text-text-secondary font-medium">ATS Compatibility Score</p>
    </div>
  );
});
