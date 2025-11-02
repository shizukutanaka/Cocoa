import React, { memo } from 'react';
import { token } from '@atlaskit/tokens';
import EmojiObjectsIcon from '@atlaskit/icon/glyph/emoji/objects';
import EditorAdvancedIcon from '@atlaskit/icon/glyph/editor/advanced';
import DownloadIcon from '@atlaskit/icon/glyph/download';

const features = [
  {
    icon: EmojiObjectsIcon,
    title: '高品質生成',
    description: '最新のAI技術により、高品質で自然なアバターを生成します',
    color: 'brand.bold'
  },
  {
    icon: EditorAdvancedIcon,
    title: '柔軟なカスタマイズ',
    description: 'スタイル、複雑さ、色、特徴を自由に組み合わせることができます',
    color: 'discovery.bold'
  },
  {
    icon: DownloadIcon,
    title: '即時ダウンロード',
    description: '生成後すぐにダウンロードして、様々なプラットフォームで使用できます',
    color: 'success.bold'
  }
] as const;

export const FeatureHighlights = memo(() => {
  return (
    <div
      style={{
        backgroundColor: token('color.background.neutral.subtle', '#F4F5F7'),
        padding: token('space.400', '32px'),
        borderRadius: '3px',
        marginTop: token('space.200', '16px')
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <h2
          style={{
            fontSize: '1.6rem',
            fontWeight: 600,
            marginBottom: token('space.300', '24px')
          }}
        >
          AI生成の特徴
        </h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: token('space.300', '24px')
          }}
        >
          {features.map((feature) => {
            const IconComponent = feature.icon;
            return (
              <div key={feature.title} style={{ textAlign: 'center' }}>
                <div
                  style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    backgroundColor: token(`color.background.${feature.color}`, '#0C66E4'),
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 16px'
                  }}
                >
                  <IconComponent
                    label={feature.title}
                    primaryColor={token('color.text.inverse', '#FFF')}
                  />
                </div>
                <h3
                  style={{
                    fontSize: '1.2rem',
                    fontWeight: 500,
                    marginBottom: token('space.100', '8px')
                  }}
                >
                  {feature.title}
                </h3>
                <p style={{ color: token('color.text.subtle', '#44546F') }}>
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});

FeatureHighlights.displayName = 'FeatureHighlights';
