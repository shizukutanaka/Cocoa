import React, { memo, useCallback } from 'react';
import { useAvatarGeneration } from '@/hooks/useAvatarGeneration';
import { useAvatarOptions } from '@/hooks/useAvatarOptions';
import { AvatarOptionsPanel } from '@/components/AvatarOptionsPanel';
import { AvatarResultPanel } from '@/components/AvatarResultPanel';
import { GenerationHistory } from '@/components/GenerationHistory';
import { FeatureHighlights } from '@/components/FeatureHighlights';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import PageHeader from '@atlaskit/page-header';
import { token } from '@atlaskit/tokens';
import { Alert, AlertProps } from '@atlaskit/alert';

const AIGenerator: React.FC = memo(() => {
  const { options, updateOption, toggleColor } = useAvatarOptions();
  const { state, generateAvatar, downloadAvatar, clearError } = useAvatarGeneration();

  const handleOptionChange = useCallback((key: keyof typeof options, value: any) => {
    updateOption(key, value);
  }, [updateOption]);

  const handleColorToggle = useCallback((color: string) => {
    toggleColor(color);
  }, [toggleColor]);

  const handleGenerate = useCallback(async () => {
    await generateAvatar();
  }, [generateAvatar]);

  const handleDownload = useCallback((avatar: any) => {
    downloadAvatar(avatar);
  }, [downloadAvatar]);

  return (
    <ErrorBoundary>
      <div
        style={{
          padding: token('space.200', '16px'),
          maxWidth: '1200px',
          margin: '0 auto',
          width: '100%'
        }}
      >
        <PageHeader>AIアバター生成</PageHeader>

        {state.error && (
          <Alert
            type="error"
            onClose={clearError}
            style={{ marginBottom: token('space.200', '16px') }}
          >
            {state.error}
          </Alert>
        )}

        <div
          style={{
            display: 'flex',
            gap: token('space.200', '16px'),
            flexDirection: 'column'
          }}
        >
          {/* 生成オプションと結果 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
              gap: token('space.200', '16px'),
              '@media (max-width: 768px)': {
                gridTemplateColumns: '1fr'
              }
            } as React.CSSProperties}
          >
            <AvatarOptionsPanel
              options={options}
              isGenerating={state.isGenerating}
              onOptionChange={handleOptionChange}
              onGenerate={handleGenerate}
            />

            <AvatarResultPanel
              avatar={state.generatedAvatar}
              onDownload={handleDownload}
            />
          </div>

          {/* 生成履歴 */}
          <div
            style={{
              backgroundColor: token('elevation.surface.raised', '#FFF'),
              padding: token('space.200', '16px'),
              borderRadius: '3px',
              boxShadow: token('elevation.shadow.raised', 'none')
            }}
          >
            <GenerationHistory history={state.history} />
          </div>
        </div>

        {/* 特徴セクション */}
        <FeatureHighlights />
      </div>
    </ErrorBoundary>
  );
});

AIGenerator.displayName = 'AIGenerator';

export default AIGenerator;
