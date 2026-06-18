import { memo } from 'react';

interface SkillBadgesProps {
  skills: string[];
  type: 'matched' | 'missing';
}

export const SkillBadges = memo(function SkillBadges({ skills, type }: SkillBadgesProps) {
  const isMatched = type === 'matched';
  const label = isMatched ? 'Matched Skills' : 'Missing Skills';

  if (skills.length === 0) return null;

  return (
    <div className="mb-3">
      <p className="text-xs font-semibold text-text-secondary mb-2 font-mono">
        {label} <span className="text-text-secondary">({skills.length})</span>
      </p>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <span
            key={skill}
            className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium ${
              isMatched
                ? 'bg-success/15 text-success'
                : 'bg-danger/15 text-danger'
            }`}
          >
            {skill}
          </span>
        ))}
      </div>
    </div>
  );
});
