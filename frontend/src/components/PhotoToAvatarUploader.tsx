import React, { useState, useCallback, useRef } from 'react';
import { GenerationOptions } from '@/types/avatarTypes';
import Button from '@atlaskit/button/standard-button';
import { token } from '@atlaskit/tokens';
import UploadIcon from '@atlaskit/icon/glyph/upload';
import ImageIcon from '@atlaskit/icon/glyph/image';

interface PhotoToAvatarUploaderProps {
  avatarOptions: GenerationOptions;
  onPhotoSelected?: (file: File) => void;
  onClose?: () => void;
}

export const PhotoToAvatarUploader: React.FC<PhotoToAvatarUploaderProps> = ({
  avatarOptions,
  onPhotoSelected,
  onClose
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // ファイルの検証
    if (!file.type.startsWith('image/')) {
      setError('画像ファイルを選択してください。');
      return;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB制限
      setError('ファイルサイズは10MB以下にしてください。');
      return;
    }

    setSelectedFile(file);
    setError(null);

    // プレビュー画像を作成
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    // 写真の品質分析を実行（シミュレーション）
    analyzePhoto(file);
  }, []);

  const analyzePhoto = async (file: File) => {
    setIsAnalyzing(true);

    try {
      // 実際の実装ではバックエンドAPIを呼び出す
      await new Promise(resolve => setTimeout(resolve, 2000));

      // シミュレートされた分析結果
      const mockAnalysis = {
        quality: 'excellent',
        face_shape: 'oval',
        features_detected: 5,
        recommendations: ['写真の品質が非常に良いです。このまま使用できます。']
      };

      setAnalysisResult(mockAnalysis);

    } catch (err) {
      setError('写真の分析に失敗しました。');
      console.error('Photo analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleGenerateAvatar = useCallback(() => {
    if (selectedFile && onPhotoSelected) {
      onPhotoSelected(selectedFile);
    }
  }, [selectedFile, onPhotoSelected]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type.startsWith('image/')) {
        setSelectedFile(file);
        setError(null);

        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
        analyzePhoto(file);
      } else {
        setError('画像ファイルを選択してください。');
      }
    }
  }, [analyzePhoto]);

  const handleRemovePhoto = useCallback(() => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setAnalysisResult(null);
    setError(null);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
  }, [previewUrl]);

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
            写真からアバター生成
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#666' }}>
            1枚の写真から高品質なAIアバターを作成します
          </p>
        </div>
        {onClose && (
          <Button appearance="subtle" onClick={onClose}>
            閉じる
          </Button>
        )}
      </div>

      <div style={{ flex: 1, padding: '20px', overflowY: 'auto' }}>
        {/* アップロードエリア */}
        <div
          style={{
            border: `2px dashed ${token('color.border', '#DFE1E6')}`,
            borderRadius: '8px',
            padding: '40px 20px',
            textAlign: 'center',
            backgroundColor: token('color.background.neutral.subtle', '#F4F5F7'),
            marginBottom: '20px',
            transition: 'all 0.3s ease',
            cursor: 'pointer'
          }}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={handleUploadClick}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          {previewUrl ? (
            <div style={{ position: 'relative' }}>
              <img
                src={previewUrl}
                alt="選択された写真"
                style={{
                  maxWidth: '100%',
                  maxHeight: '200px',
                  borderRadius: '8px',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
                }}
              />
              <Button
                appearance="danger"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemovePhoto();
                }}
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px'
                }}
              >
                削除
              </Button>
            </div>
          ) : (
            <div>
              <ImageIcon size="large" />
              <p style={{
                margin: '16px 0 8px 0',
                fontSize: '1.1rem',
                color: '#333',
                fontWeight: 600
              }}>
                写真をアップロードまたはドラッグ&ドロップ
              </p>
              <p style={{
                margin: 0,
                fontSize: '0.9rem',
                color: '#666'
              }}>
                JPG、PNG、またはBMP形式、最大10MB
              </p>
            </div>
          )}
        </div>

        {/* エラーメッセージ */}
        {error && (
          <div style={{
            padding: '12px 16px',
            backgroundColor: token('color.background.warning', '#FFF3CD'),
            color: token('color.text.warning', '#856404'),
            borderRadius: '4px',
            marginBottom: '16px',
            fontSize: '0.9rem'
          }}>
            {error}
          </div>
        )}

        {/* 分析結果 */}
        {isAnalyzing && (
          <div style={{
            padding: '16px',
            backgroundColor: token('color.background.neutral.subtle', '#F4F5F7'),
            borderRadius: '8px',
            marginBottom: '16px',
            textAlign: 'center'
          }}>
            <p style={{ margin: 0, color: '#666' }}>
              写真を分析中...
            </p>
          </div>
        )}

        {analysisResult && !isAnalyzing && (
          <div style={{
            padding: '16px',
            backgroundColor: token('color.background.success.subtle', '#E3FCEF'),
            borderRadius: '8px',
            marginBottom: '16px',
            border: `1px solid ${token('color.border.success', '#36B37E')}`
          }}>
            <h3 style={{ margin: '0 0 12px 0', color: '#333', fontSize: '1rem' }}>
              📸 写真分析結果
            </h3>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: 600, color: '#333' }}>
                  品質評価
                </div>
                <div style={{
                  fontSize: '1.2rem',
                  fontWeight: 'bold',
                  color: analysisResult.quality === 'excellent' ? '#28a745' :
                         analysisResult.quality === 'good' ? '#ffc107' : '#dc3545'
                }}>
                  {analysisResult.quality === 'excellent' ? '優秀' :
                   analysisResult.quality === 'good' ? '良好' : '普通'}
                </div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: 600, color: '#333' }}>
                  顔形状
                </div>
                <div style={{ fontSize: '1rem', color: '#666' }}>
                  {analysisResult.face_shape === 'oval' ? '卵型' :
                   analysisResult.face_shape === 'round' ? '丸型' :
                   analysisResult.face_shape === 'heart' ? 'ハート型' : '不明'}
                </div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: 600, color: '#333' }}>
                  特徴検出数
                </div>
                <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#007bff' }}>
                  {analysisResult.features_detected}
                </div>
              </div>
            </div>

            {analysisResult.recommendations && (
              <div style={{ marginTop: '12px' }}>
                <div style={{ fontWeight: 600, color: '#333', marginBottom: '8px' }}>
                  推奨事項:
                </div>
                <ul style={{ margin: 0, paddingLeft: '20px', color: '#666' }}>
                  {analysisResult.recommendations.map((rec: string, index: number) => (
                    <li key={index} style={{ marginBottom: '4px' }}>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* アバター設定プレビュー */}
        <div style={{
          padding: '16px',
          backgroundColor: token('color.background.neutral.subtle', '#F4F5F7'),
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1rem', color: '#333' }}>
            生成設定プレビュー
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px'
          }}>
            <div>
              <div style={{ fontWeight: 600, color: '#333', marginBottom: '4px' }}>
                ターゲットスタイル
              </div>
              <div style={{ color: '#666' }}>
                {avatarOptions.style === 'realistic' ? 'リアル' :
                 avatarOptions.style === 'anime' ? 'アニメ' :
                 avatarOptions.style === 'cartoon' ? 'カートゥーン' :
                 avatarOptions.style === 'professional' ? 'プロフェッショナル' :
                 avatarOptions.style === 'artistic' ? 'アーティスティック' : 'リアル'}
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#333', marginBottom: '4px' }}>
                品質レベル
              </div>
              <div style={{ color: '#666' }}>
                {avatarOptions.complexity === 'simple' ? 'シンプル' :
                 avatarOptions.complexity === 'moderate' ? '標準' :
                 avatarOptions.complexity === 'complex' ? '複雑' :
                 avatarOptions.complexity === 'high-performance' ? '高性能' :
                 avatarOptions.complexity === 'ultra-detailed' ? '超詳細' : '標準'}
              </div>
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#333', marginBottom: '4px' }}>
                特徴強調
              </div>
              <div style={{ color: '#666' }}>
                顔の特徴を強調する
              </div>
            </div>
          </div>
        </div>

        {/* 生成ボタン */}
        <div style={{ textAlign: 'center' }}>
          <Button
            appearance="primary"
            size="large"
            onClick={handleGenerateAvatar}
            isDisabled={!selectedFile || !analysisResult || isAnalyzing}
            iconBefore={<UploadIcon label="生成" />}
            style={{ padding: '12px 24px', fontSize: '1.1rem' }}
          >
            アバターを生成
          </Button>

          {!selectedFile && (
            <p style={{
              margin: '12px 0 0 0',
              fontSize: '0.9rem',
              color: '#666'
            }}>
              まず写真を選択してください
            </p>
          )}
        </div>

        {/* 使い方ガイド */}
        <div style={{
          marginTop: '32px',
          padding: '20px',
          backgroundColor: '#f8f9fa',
          borderRadius: '8px',
          border: '1px dashed #dee2e6'
        }}>
          <h3 style={{ margin: '0 0 16px 0', color: '#6c757d', fontSize: '1.1rem' }}>
            使い方ガイド
          </h3>
          <ol style={{
            margin: 0,
            paddingLeft: '24px',
            color: '#6c757d',
            lineHeight: 1.6
          }}>
            <li>正面を向いた鮮明な写真をアップロードしてください</li>
            <li>システムが自動的に顔の特徴を分析します</li>
            <li>分析結果を確認し、必要に応じて別の写真を試してください</li>
            <li>ターゲットスタイルと設定を確認してください</li>
            <li>「アバターを生成」ボタンをクリックしてAIアバターを作成してください</li>
          </ol>

          <div style={{
            marginTop: '16px',
            padding: '12px',
            backgroundColor: '#fff3cd',
            borderRadius: '4px',
            fontSize: '0.9rem',
            color: '#856404'
          }}>
            <strong>ヒント:</strong> より良い結果を得るために、明るい場所で撮影した正面からの写真を使用してください。
          </div>
        </div>
      </div>
    </div>
  );
};
