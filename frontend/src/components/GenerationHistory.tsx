import React, { memo } from 'react';
import { token } from '@atlaskit/tokens';
import { GenerationHistoryItem } from '@/types/avatarTypes';

interface GenerationHistoryProps {
  history: GenerationHistoryItem[];
}

export const GenerationHistory = memo<GenerationHistoryProps>(({ history }) => {
  if (history.length === 0) {
    return null;
  }

  return (
    <div>
      <h3
        style={{
          fontSize: '1.2rem',
          fontWeight: 500,
          marginTop: token('space.300', '24px'),
          marginBottom: token('space.100', '8px')
        }}
      >
        生成履歴
      </h3>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: token('space.100', '8px')
        }}
      >
        {history.map((item) => (
          <div
            key={item.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: token('space.150', '12px'),
              padding: token('space.100', '8px'),
              backgroundColor: token('color.background.neutral', '#F4F5F7'),
              borderRadius: '3px'
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: token('color.background.brand.bold', '#0C66E4'),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFF',
                fontWeight: 500
              }}
            >
              {item.avatar.name.charAt(0).toUpperCase()}
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontWeight: 500 }}>{item.avatar.name}</p>
              <p
                style={{
                  fontSize: '0.8rem',
                  color: token('color.text.subtlest', '#6B778C')
                }}
              >
                {new Date(item.timestamp).toLocaleDateString('ja-JP', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});

GenerationHistory.displayName = 'GenerationHistory';
