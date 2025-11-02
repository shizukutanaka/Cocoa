import React, { memo } from 'react';
import { token } from '@atlaskit/tokens';

interface LoadingSkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  className?: string;
}

export const LoadingSkeleton = memo<LoadingSkeletonProps>(({
  width = '100%',
  height = '1rem',
  borderRadius = '3px',
  className
}) => {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        borderRadius,
        background: `linear-gradient(90deg, ${token('color.background.neutral', '#F4F5F7')} 25%, ${token('color.background.neutral.hovered', '#EBECF0')} 50%, ${token('color.background.neutral', '#F4F5F7')} 75%)`,
        backgroundSize: '200% 100%',
        animation: 'loading 1.5s infinite',
      }}
    />
  );
});

LoadingSkeleton.displayName = 'LoadingSkeleton';
