import React from 'react';

interface LiveTermLogProps {
  description: string;
}

export function LiveTermLog({ description }: LiveTermLogProps) {
  return (
    <div className="compact-desc">
      {description}
    </div>
  );
}
