import React, { useState, useCallback, useRef, useEffect } from 'react';
import { GenerationOptions } from '@/types/avatarTypes';
import Button from '@atlaskit/button/standard-button';
import TextArea from '@atlaskit/textarea';
import Select from '@atlaskit/select';
import { token } from '@atlaskit/tokens';
import PlayIcon from '@atlaskit/icon/glyph/media-services/play';
import PauseIcon from '@atlaskit/icon/glyph/media-services/pause';

interface AvatarVideoCreatorProps {
  avatarOptions: GenerationOptions;
  onClose?: () => void;
}

interface VideoTemplate {
  id: string;
  name: string;
  description: string;
  preview_image: string;
}

const VIDEO_TEMPLATES: VideoTemplate[] = [
  {
    id: 'presentation',
    name: 'プレゼンテーション',
    description: 'ビジネスプレゼンテーション向けスタイル',
    preview_image: 'presentation_preview.jpg'
  },
  {
    id: 'tutorial',
    name: 'チュートリアル',
    description: '教育・学習コンテンツ向けスタイル',
    preview_image: 'tutorial_preview.jpg'
  },
  {
    id: 'storytelling',
    name: 'ストーリーテリング',
    description: '物語・ナラティブ向けスタイル',
    preview_image: 'storytelling_preview.jpg'
  },
  {
    id: 'interview',
    name: 'インタビュー',
    description: '対談・インタビュー向けスタイル',
    preview_image: 'interview_preview.jpg'
  }
];

const LANGUAGE_OPTIONS = [
  { label: '日本語', value: 'ja' },
  { label: '英語', value: 'en' },
  { label: '中国語', value: 'zh' },
  { label: '韓国語', value: 'ko' },
  { label: 'スペイン語', value: 'es' },
  { label: 'フランス語', value: 'fr' },
  { label: 'ドイツ語', value: 'de' }
];

const RESOLUTION_OPTIONS = [
  { label: 'フルHD (1920x1080)', value: '1920x1080' },
  { label: 'HD (1280x720)', value: '1280x720' },
  { label: 'SD (854x480)', value: '854x480' }
];

export const AvatarVideoCreator: React.FC<AvatarVideoCreatorProps> = ({
  avatarOptions,
  onClose
}) => {
  const [scriptText, setScriptText] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<VideoTemplate>(VIDEO_TEMPLATES[0]);
  const [selectedLanguage, setSelectedLanguage] = useState(LANGUAGE_OPTIONS[0]);
  const [selectedResolution, setSelectedResolution] = useState(RESOLUTION_OPTIONS[0]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedVideo, setGeneratedVideo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState('');

  const videoRef = useRef<HTMLVideoElement>(null);

  const handleGenerateVideo = async () => {
    if (!scriptText.trim()) {
      setError('スクリプトを入力してください。');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setGeneratedVideo(null);

    try {
      // 実際の実装ではバックエンドAPIを呼び出す
      await new Promise(resolve => setTimeout(resolve, 3000));

      // シミュレートされた動画生成
      const mockVideoUrl = `mock_video_${Date.now()}.mp4`;
      setGeneratedVideo(mockVideoUrl);
      setError(null);

    } catch (err) {
      setError('動画の生成に失敗しました。もう一度お試しください。');
      console.error('Video generation error:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePreviewText = useCallback(() => {
    if (scriptText.length > 100) {
      setPreviewText(scriptText.substring(0, 100) + '...');
    } else {
      setPreviewText(scriptText);
    }
  }, [scriptText]);

  useEffect(() => {
    handlePreviewText();
  }, [handlePreviewText]);

  const handlePlayVideo = () => {
    if (videoRef.current) {
      videoRef.current.play();
    }
  };

  const handlePauseVideo = () => {
    if (videoRef.current) {
      videoRef.current.pause();
    }
  };

  const estimatedDuration = Math.ceil(scriptText.length / 150); // 簡易計算

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'white'
    }}>
      {/* ヘッダー */}
      <div style={{
        padding: '20px',
        borderBottom: `1px solid ${token('color.border', '#DFE1E6')}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.3rem', color: '#333' }}>
            アバター動画作成
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#666' }}>
            アバターを使った動画を生成します
          </p>
        </div>
        {onClose && (
          <Button appearance="subtle" onClick={onClose}>
            閉じる
          </Button>
        )}
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* 左側: 設定パネル */}
        <div style={{
          width: '300px',
          padding: '20px',
          borderRight: `1px solid ${token('color.border', '#DFE1E6')}`,
          overflowY: 'auto'
        }}>
          {/* スクリプト入力 */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontWeight: 600,
              color: '#333'
            }}>
              スクリプトテキスト *
            </label>
            <TextArea
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              placeholder="動画で読み上げたいスクリプトを入力してください..."
              minRows={6}
              maxRows={12}
              style={{ width: '100%' }}
            />
            <div style={{
              fontSize: '0.8rem',
              color: '#666',
              marginTop: '4px',
              textAlign: 'right'
            }}>
              文字数: {scriptText.length} | 推定時間: {estimatedDuration}秒
            </div>
          </div>

          {/* 動画スタイル選択 */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontWeight: 600,
              color: '#333'
            }}>
              動画スタイル
            </label>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '8px'
            }}>
              {VIDEO_TEMPLATES.map((template) => (
                <button
                  key={template.id}
                  onClick={() => setSelectedTemplate(template)}
                  style={{
                    padding: '12px 8px',
                    border: selectedTemplate.id === template.id
                      ? `2px solid ${token('color.border.focused', '#0962F3')}`
                      : `1px solid ${token('color.border', '#DFE1E6')}`,
                    borderRadius: '6px',
                    backgroundColor: selectedTemplate.id === template.id
                      ? token('color.background.selected', '#E6F3FF')
                      : 'white',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    {template.name}
                  </div>
                  <div style={{
                    fontSize: '0.8rem',
                    color: '#666',
                    marginTop: '2px'
                  }}>
                    {template.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 言語選択 */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontWeight: 600,
              color: '#333'
            }}>
              音声言語
            </label>
            <Select
              options={LANGUAGE_OPTIONS}
              value={selectedLanguage}
              onChange={(value) => value && setSelectedLanguage(value)}
              placeholder="言語を選択"
            />
          </div>

          {/* 解像度選択 */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              marginBottom: '8px',
              fontWeight: 600,
              color: '#333'
            }}>
              動画解像度
            </label>
            <Select
              options={RESOLUTION_OPTIONS}
              value={selectedResolution}
              onChange={(value) => value && setSelectedResolution(value)}
              placeholder="解像度を選択"
            />
          </div>

          {/* 生成ボタン */}
          <Button
            appearance="primary"
            onClick={handleGenerateVideo}
            isDisabled={!scriptText.trim() || isGenerating}
            isLoading={isGenerating}
            style={{ width: '100%' }}
            iconBefore={isGenerating ? undefined : <PlayIcon label="生成" />}
          >
            {isGenerating ? '動画を生成中...' : '動画を生成'}
          </Button>

          {error && (
            <div style={{
              marginTop: '12px',
              padding: '8px 12px',
              backgroundColor: token('color.background.warning', '#FFF3CD'),
              color: token('color.text.warning', '#856404'),
              borderRadius: '4px',
              fontSize: '0.9rem'
            }}>
              {error}
            </div>
          )}
        </div>

        {/* 右側: プレビューと結果 */}
        <div style={{ flex: 1, padding: '20px', overflowY: 'auto' }}>
          {/* アバター情報 */}
          <div style={{
            marginBottom: '20px',
            padding: '16px',
            backgroundColor: token('color.background.neutral.subtle', '#F4F5F7'),
            borderRadius: '8px'
          }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#333' }}>
              使用するアバター
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: avatarOptions.colors[0] || '#3B82F6',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.5rem',
                color: 'white',
                fontWeight: 'bold'
              }}>
                {avatarOptions.style.charAt(0).toUpperCase()}
              </div>
              <div>
                <div style={{ fontWeight: 600, color: '#333' }}>
                  {avatarOptions.style}スタイル
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  複雑さ: {avatarOptions.complexity} |
                  色: {avatarOptions.colors.length}色
                </div>
              </div>
            </div>
          </div>

          {/* スクリプトプレビュー */}
          {scriptText && (
            <div style={{
              marginBottom: '20px',
              padding: '16px',
              backgroundColor: '#f8f9fa',
              borderRadius: '8px',
              border: '1px solid #e9ecef'
            }}>
              <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#333' }}>
                スクリプトプレビュー
              </h3>
              <div style={{
                fontSize: '0.9rem',
                lineHeight: 1.5,
                color: '#495057',
                maxHeight: '120px',
                overflowY: 'auto'
              }}>
                {previewText}
              </div>
            </div>
          )}

          {/* 生成結果 */}
          {generatedVideo && (
            <div style={{
              padding: '16px',
              backgroundColor: token('color.background.success', '#E3FCEF'),
              borderRadius: '8px',
              border: `1px solid ${token('color.border.success', '#36B37E')}`
            }}>
              <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#333' }}>
                🎉 動画が生成されました！
              </h3>

              {/* 動画プレーヤー（シミュレーション） */}
              <div style={{
                width: '100%',
                height: '200px',
                backgroundColor: '#000',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '12px',
                position: 'relative'
              }}>
                <video
                  ref={videoRef}
                  style={{
                    width: '100%',
                    height: '100%',
                    borderRadius: '8px'
                  }}
                  controls
                >
                  <source src={`/api/videos/${generatedVideo}`} type="video/mp4" />
                  お使いのブラウザは動画タグをサポートしていません。
                </video>

                {/* 動画コントロールオーバーレイ（シミュレーション） */}
                <div style={{
                  position: 'absolute',
                  bottom: '10px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  display: 'flex',
                  gap: '8px'
                }}>
                  <Button
                    appearance="subtle"
                    size="small"
                    onClick={handlePlayVideo}
                    style={{ color: 'white' }}
                  >
                    <PlayIcon label="再生" size="small" />
                  </Button>
                  <Button
                    appearance="subtle"
                    size="small"
                    onClick={handlePauseVideo}
                    style={{ color: 'white' }}
                  >
                    <PauseIcon label="一時停止" size="small" />
                  </Button>
                </div>
              </div>

              <div style={{
                display: 'flex',
                gap: '8px',
                flexWrap: 'wrap'
              }}>
                <Button appearance="primary" size="small">
                  ダウンロード
                </Button>
                <Button appearance="subtle" size="small">
                  共有
                </Button>
                <Button appearance="subtle" size="small">
                  編集
                </Button>
              </div>

              <div style={{
                marginTop: '12px',
                fontSize: '0.8rem',
                color: '#666'
              }}>
                解像度: {selectedResolution.label} |
                言語: {selectedLanguage.label} |
                スタイル: {selectedTemplate.name} |
                推定時間: {estimatedDuration}秒
              </div>
            </div>
          )}

          {/* 使い方ガイド */}
          {!scriptText && !generatedVideo && (
            <div style={{
              padding: '20px',
              backgroundColor: '#f8f9fa',
              borderRadius: '8px',
              border: '1px dashed #dee2e6'
            }}>
              <h3 style={{ margin: '0 0 12px 0', color: '#6c757d' }}>
                使い方
              </h3>
              <ol style={{
                margin: 0,
                paddingLeft: '20px',
                color: '#6c757d',
                lineHeight: 1.6
              }}>
                <li>左側のパネルで動画のスクリプトを入力してください</li>
                <li>動画スタイルを選択してください</li>
                <li>音声言語と解像度を設定してください</li>
                <li>「動画を生成」ボタンをクリックしてください</li>
                <li>生成された動画をプレビュー・ダウンロードできます</li>
              </ol>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
