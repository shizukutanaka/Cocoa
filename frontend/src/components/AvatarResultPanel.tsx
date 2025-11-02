import React, { memo, useCallback } from 'react';
import Button from '@atlaskit/button/standard-button';
import { token } from '@atlaskit/tokens';
import ImageIcon from '@atlaskit/icon/glyph/image';
import DownloadIcon from '@atlaskit/icon/glyph/download';
import { GeneratedAvatar } from '@/types/avatarTypes';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';

interface AvatarResultPanelProps {
  avatar: GeneratedAvatar | null;
  onDownload: (avatar: GeneratedAvatar) => void;
}

export const AvatarResultPanel = memo<AvatarResultPanelProps>(({ avatar, onDownload }) => {
  const handleDownload = useCallback(() => {
    if (avatar) {
      onDownload(avatar);
    }
  }, [avatar, onDownload]);

  return (
    <div
      style={{
        backgroundColor: token('elevation.surface.raised', '#FFF'),
        padding: token('space.200', '16px'),
        borderRadius: '3px',
        boxShadow: token('elevation.shadow.raised', 'none')
      }}
    >
      <h2
        style={{
          fontSize: '1.4rem',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: token('space.100', '8px'),
          marginBottom: token('space.300', '24px')
        }}
      >
        <ImageIcon label="result" />
        生成結果
      </h2>

      <div
        style={{
          aspectRatio: '1',
          backgroundColor: token('color.background.neutral', '#F4F5F7'),
          borderRadius: '3px',
          marginBottom: token('space.200', '16px'),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        {avatar ? (
          <div style={{ textAlign: 'center', padding: token('space.200', '16px') }}>
            <div
              style={{
                width: '120px',
                height: '120px',
                borderRadius: '50%',
                backgroundColor: token('color.background.brand.bold', '#0C66E4'),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
                fontSize: '3rem',
                fontWeight: 'bold',
                color: 'white'
              }}
            >
              {avatar.name.charAt(0).toUpperCase()}
            </div>
            <h3
              style={{
                fontSize: '1.2rem',
                fontWeight: 500,
                marginTop: token('space.200', '16px')
              }}
            >
              {avatar.name}
            </h3>
            <p
              style={{
                color: token('color.text.subtlest', '#6B778C'),
                marginBottom: token('space.200', '16px')
              }}
            >
              AIによって生成されたアバター
            </p>
            <div style={{ display: 'flex', gap: token('space.100', '8px') }}>
              <Button
                iconBefore={<DownloadIcon label="download" />}
                onClick={handleDownload}
              >
                ダウンロード
              </Button>
              <Button>カスタマイズ</Button>
            </div>
          </div>
        ) : (
          <div
            style={{
              textAlign: 'center',
              color: token('color.text.subtlest', '#6B778C'),
              width: '100%',
              padding: token('space.200', '16px')
            }}
          >
            <div style={{ marginBottom: token('space.200', '16px') }}>
              <LoadingSkeleton width="80px" height="80px" borderRadius="50%" />
            </div>
            <LoadingSkeleton width="60%" height="1.2rem" className="mb-2" />
            <LoadingSkeleton width="80%" height="1rem" className="mb-4" />
            <div style={{ display: 'flex', gap: token('space.100', '8px'), justifyContent: 'center' }}>
              <LoadingSkeleton width="100px" height="32px" borderRadius="6px" />
              <LoadingSkeleton width="100px" height="32px" borderRadius="6px" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

AvatarResultPanel.displayName = 'AvatarResultPanel';
