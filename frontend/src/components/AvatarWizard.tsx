import React, { useState, useCallback } from 'react';
import { GenerationOptions } from '@/types/avatarTypes';
import { AVATAR_STYLES, COMPLEXITY_LEVELS, COLOR_PALETTE } from '@/constants/avatarConstants';
import { DraggableColorPalette } from './DraggableColorPalette';

interface WizardStep {
  id: string;
  title: string;
  description: string;
  component: React.ReactNode;
}

interface AvatarWizardProps {
  onComplete: (options: GenerationOptions) => void;
  onCancel: () => void;
}

export const AvatarWizard: React.FC<AvatarWizardProps> = ({ onComplete, onCancel }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [options, setOptions] = useState<GenerationOptions>({
    style: 'realistic',
    complexity: 'moderate',
    colors: ['#3B82F6'],
    features: {
      hair: true,
      eyes: true,
      mouth: true,
      accessories: false
    }
  });

  const updateOptions = useCallback((updates: Partial<GenerationOptions>) => {
    setOptions(prev => ({ ...prev, ...updates }));
  }, []);

  const nextStep = useCallback(() => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      onComplete(options);
    }
  }, [currentStep, options, onComplete]);

  const prevStep = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  }, [currentStep]);

  const steps: WizardStep[] = [
    {
      id: 'welcome',
      title: 'アバター作成へようこそ',
      description: '簡単に魅力的なアバターを作成しましょう',
      component: (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <h2 style={{ fontSize: '2rem', marginBottom: '20px', color: '#333' }}>
            アバター作成を始めましょう！
          </h2>
          <p style={{ fontSize: '1.1rem', color: '#666', marginBottom: '30px' }}>
            ステップバイステップで、あなただけのオリジナルアバターを作成できます
          </p>
          <div style={{
            backgroundColor: '#f0f8ff',
            padding: '20px',
            borderRadius: '8px',
            marginBottom: '30px'
          }}>
            <h3 style={{ color: '#3B82F6', marginBottom: '15px' }}>
              このウィザードでできること：
            </h3>
            <ul style={{ textAlign: 'left', maxWidth: '400px', margin: '0 auto' }}>
              <li>スタイルの選択（リアル、アニメ、カートゥーンなど）</li>
              <li>複雑さレベルの設定</li>
              <li>カラーパレットの選択</li>
              <li>特徴の有効化/無効化</li>
              <li>リアルタイムプレビュー</li>
            </ul>
          </div>
        </div>
      )
    },
    {
      id: 'style',
      title: 'スタイルを選択',
      description: 'アバターの基本的なスタイルを選びましょう',
      component: (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '20px', color: '#333' }}>
            アバターのスタイルを選択してください
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '15px',
            marginBottom: '20px'
          }}>
            {AVATAR_STYLES.map((style) => (
              <button
                key={style.value}
                onClick={() => updateOptions({ style: style.value as any })}
                style={{
                  padding: '20px',
                  border: options.style === style.value ? '3px solid #3B82F6' : '2px solid #ddd',
                  borderRadius: '8px',
                  backgroundColor: options.style === style.value ? '#f0f8ff' : 'white',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
                  {style.label}
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  {getStyleDescription(style.value)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )
    },
    {
      id: 'complexity',
      title: '複雑さを設定',
      description: 'アバターの詳細度を選びましょう',
      component: (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '20px', color: '#333' }}>
            アバターの複雑さレベルを選択してください
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '15px'
          }}>
            {COMPLEXITY_LEVELS.map((level) => (
              <button
                key={level.value}
                onClick={() => updateOptions({ complexity: level.value as any })}
                style={{
                  padding: '20px',
                  border: options.complexity === level.value ? '3px solid #3B82F6' : '2px solid #ddd',
                  borderRadius: '8px',
                  backgroundColor: options.complexity === level.value ? '#f0f8ff' : 'white',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
                  {level.label}
                </div>
                <div style={{ fontSize: '0.9rem', color: '#666' }}>
                  {getComplexityDescription(level.value)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )
    },
    {
      id: 'colors',
      title: 'カラーパレットを選択',
      description: 'アバターの色を設定しましょう',
      component: (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '20px', color: '#333' }}>
            アバターのカラーパレットを選択してください（最大4色）
          </h3>
          <DraggableColorPalette
            selectedColors={options.colors}
            onColorsChange={(newColors) => updateOptions({ colors: newColors })}
          />
          <div style={{ marginTop: '15px', fontSize: '0.9rem', color: '#666' }}>
            選択された色: {options.colors.length}色
          </div>
        </div>
      )
    },
    {
      id: 'features',
      title: '特徴を選択',
      description: 'アバターに含める特徴を選びましょう',
      component: (
        <div style={{ padding: '20px' }}>
          <h3 style={{ marginBottom: '20px', color: '#333' }}>
            アバターに含める特徴を選択してください
          </h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '15px'
          }}>
            {Object.entries(options.features).map(([feature, enabled]) => (
              <button
                key={feature}
                onClick={() => updateOptions({
                  features: {
                    ...options.features,
                    [feature]: !enabled
                  }
                })}
                style={{
                  padding: '15px',
                  border: enabled ? '3px solid #10B981' : '2px solid #ddd',
                  borderRadius: '8px',
                  backgroundColor: enabled ? '#f0fff4' : 'white',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{
                  fontWeight: 'bold',
                  color: enabled ? '#10B981' : '#333'
                }}>
                  {getFeatureLabel(feature)}
                </div>
                <div style={{
                  fontSize: '0.9rem',
                  color: '#666',
                  marginTop: '5px'
                }}>
                  {enabled ? '有効' : '無効'}
                </div>
              </button>
            ))}
          </div>
        </div>
      )
    },
    {
      id: 'preview',
      title: 'プレビューを確認',
      description: '作成するアバターのプレビューを確認しましょう',
      component: (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h3 style={{ marginBottom: '20px', color: '#333' }}>
            アバターのプレビュー
          </h3>
          <div style={{
            width: '300px',
            height: '300px',
            margin: '0 auto 20px',
            border: '2px solid #ddd',
            borderRadius: '8px',
            backgroundColor: '#f8f9fa',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <div style={{
              fontSize: '1.2rem',
              color: '#666'
            }}>
              プレビュー表示領域
            </div>
          </div>
          <div style={{
            backgroundColor: '#f0f8ff',
            padding: '15px',
            borderRadius: '8px',
            marginBottom: '20px'
          }}>
            <h4 style={{ marginBottom: '10px', color: '#3B82F6' }}>
              選択された設定：
            </h4>
            <p>スタイル: {AVATAR_STYLES.find(s => s.value === options.style)?.label}</p>
            <p>複雑さ: {COMPLEXITY_LEVELS.find(c => c.value === options.complexity)?.label}</p>
            <p>色: {options.colors.length}色選択済み</p>
            <p>特徴: {Object.values(options.features).filter(Boolean).length}つ有効</p>
          </div>
        </div>
      )
    }
  ];

  return (
    <div style={{
      maxWidth: '800px',
      margin: '0 auto',
      backgroundColor: 'white',
      borderRadius: '12px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      overflow: 'hidden'
    }}>
      {/* ヘッダー */}
      <div style={{
        backgroundColor: '#3B82F6',
        color: 'white',
        padding: '20px',
        textAlign: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.8rem' }}>
          アバター作成ウィザード
        </h1>
        <p style={{ margin: '8px 0 0 0', opacity: 0.9 }}>
          ステップ {currentStep + 1} / {steps.length}: {steps[currentStep].title}
        </p>
      </div>

      {/* プログレスバー */}
      <div style={{
        backgroundColor: '#f8f9fa',
        padding: '15px 20px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '8px'
        }}>
          {steps.map((_, index) => (
            <div
              key={index}
              style={{
                width: '40px',
                height: '8px',
                backgroundColor: index <= currentStep ? '#3B82F6' : '#ddd',
                borderRadius: '4px',
                transition: 'background-color 0.3s ease'
              }}
            />
          ))}
        </div>
      </div>

      {/* コンテンツ */}
      <div style={{
        minHeight: '400px',
        padding: '20px'
      }}>
        {steps[currentStep].component}
      </div>

      {/* フッター */}
      <div style={{
        backgroundColor: '#f8f9fa',
        padding: '20px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <button
          onClick={onCancel}
          style={{
            padding: '10px 20px',
            backgroundColor: '#6B7280',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer'
          }}
        >
          キャンセル
        </button>

        <div style={{ display: 'flex', gap: '10px' }}>
          {currentStep > 0 && (
            <button
              onClick={prevStep}
              style={{
                padding: '10px 20px',
                backgroundColor: '#E5E7EB',
                color: '#374151',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              戻る
            </button>
          )}

          <button
            onClick={nextStep}
            style={{
              padding: '10px 20px',
              backgroundColor: '#3B82F6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            {currentStep === steps.length - 1 ? '完了' : '次へ'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ヘルパー関数
function getStyleDescription(style: string): string {
  const descriptions: Record<string, string> = {
    'realistic': '実在の人物のようなリアルな外見',
    'anime': '日本のアニメスタイル',
    'cartoon': '明るく楽しいカートゥーンスタイル',
    'minimalist': 'シンプルで洗練されたデザイン',
    'vr-ready': 'VR環境に最適化されたスタイル',
    'nft-compatible': 'NFTとして利用可能なデザイン',
    'metaverse-optimized': 'メタバース環境に最適化'
  };
  return descriptions[style] || '標準スタイル';
}

function getComplexityDescription(complexity: string): string {
  const descriptions: Record<string, string> = {
    'simple': '軽量で高速な表示',
    'moderate': 'バランスの取れた品質',
    'complex': '詳細な表現',
    'high-performance': '高品質で滑らかな動き',
    'ultra-detailed': '最高レベルの詳細表現'
  };
  return descriptions[complexity] || '標準レベル';
}

function getFeatureLabel(feature: string): string {
  const labels: Record<string, string> = {
    hair: '髪型',
    eyes: '目',
    mouth: '口',
    accessories: 'アクセサリー'
  };
  return labels[feature] || feature;
}
