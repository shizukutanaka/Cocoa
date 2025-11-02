import React from 'react';
import { token } from '@atlaskit/tokens';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
  message = '読み込み中...'
}) => {
  const sizeMap = {
    small: '16px',
    medium: '24px',
    large: '32px',
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: token('space.200', '16px'),
        gap: token('space.100', '8px'),
      }}
      role="status"
      aria-live="polite"
    >
      <div
        style={{
          width: sizeMap[size],
          height: sizeMap[size],
          border: `2px solid ${token('color.border', '#DFE1E6')}`,
          borderTop: `2px solid ${token('color.border.focused', '#0052CC')}`,
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }}
        aria-hidden="true"
      />
      {message && (
        <p
          style={{
            margin: 0,
            color: token('color.text.subtle', '#5E6C84'),
            fontSize: '0.875rem',
          }}
        >
          {message}
        </p>
      )}
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
