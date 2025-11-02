import React, { memo, useCallback, useMemo } from 'react';
import Form, { Field, FormFooter } from '@atlaskit/form';
import Button from '@atlaskit/button/standard-button';
import { Checkbox } from '@atlaskit/checkbox';
import { token } from '@atlaskit/tokens';
import SettingsIcon from '@atlaskit/icon/glyph/settings';
import RefreshIcon from '@atlaskit/icon/glyph/refresh';
import EmojiObjectsIcon from '@atlaskit/icon/glyph/emoji/objects';
import { AVATAR_STYLES, COMPLEXITY_LEVELS, COLOR_PALETTE, FEATURE_LABELS } from '@/constants/avatarConstants';
import { GenerationOptions } from '@/types/avatarTypes';
import { validateAvatarOptions } from '@/utils/validation';
import { DraggableColorPalette } from './DraggableColorPalette';

interface AvatarOptionsPanelProps {
  options: GenerationOptions;
  isGenerating: boolean;
  onOptionChange: (key: keyof GenerationOptions, value: any) => void;
  onGenerate: () => void;
}

export const AvatarOptionsPanel = memo<AvatarOptionsPanelProps>(({
  options,
  isGenerating,
  onOptionChange,
  onGenerate
}) => {
  const validation = useMemo(() => validateAvatarOptions(options), [options]);

  const handleStyleChange = useCallback((style: string) => {
    onOptionChange('style', style);
  }, [onOptionChange]);

  const handleComplexityChange = useCallback((complexity: string) => {
    onOptionChange('complexity', complexity);
  }, [onOptionChange]);

  const handleColorToggle = useCallback((color: string) => {
    const newColors = options.colors.includes(color as any)
      ? options.colors.filter(c => c !== color)
      : [...options.colors, color];
    onOptionChange('colors', newColors.slice(0, 4));
  }, [options.colors, onOptionChange]);

  const handleFeatureChange = useCallback((feature: keyof GenerationOptions['features'], checked: boolean) => {
    onOptionChange('features', {
      ...options.features,
      [feature]: checked
    });
  }, [options.features, onOptionChange]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent, action: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);

  const handleFormSubmit = useCallback(() => {
    if (validation.isValid) {
      onGenerate();
    }
  }, [validation.isValid, onGenerate]);

  return (
    <div
      style={{
        backgroundColor: token('elevation.surface.raised', '#FFF'),
        padding: token('space.200', '16px'),
        borderRadius: '3px',
        boxShadow: token('elevation.shadow.raised', 'none')
      }}
      role="region"
      aria-labelledby="options-heading"
    >
      <h2
        id="options-heading"
        style={{
          fontSize: '1.4rem',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: token('space.100', '8px'),
          marginBottom: token('space.300', '24px')
        }}
      >
        <SettingsIcon label="options" />
        生成オプション
      </h2>

      {!validation.isValid && (
        <div
          style={{
            backgroundColor: token('color.background.warning', '#FFF3CD'),
            border: `1px solid ${token('color.border.warning', '#FFC107')}`,
            borderRadius: '3px',
            padding: token('space.100', '8px'),
            marginBottom: token('space.200', '16px'),
            color: token('color.text.warning', '#856404')
          }}
          role="alert"
          aria-live="polite"
        >
          <ul style={{ margin: 0, paddingLeft: token('space.200', '16px') }}>
            {validation.errors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      <Form onSubmit={handleFormSubmit}>
        {({ formProps }) => (
          <form {...formProps} noValidate>
            <Field name="style" label="アバタースタイル" isRequired>
              {() => (
                <fieldset>
                  <legend style={{ marginBottom: token('space.100', '8px'), fontWeight: 500 }}>
                    アバタースタイルを選択してください
                  </legend>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: token('space.100', '8px')
                    }}
                    role="radiogroup"
                    aria-labelledby="style-legend"
                  >
                    {AVATAR_STYLES.map((style) => (
                      <Button
                        key={style.value}
                        isSelected={options.style === style.value}
                        onClick={() => handleStyleChange(style.value)}
                        onKeyDown={(e) => handleKeyDown(e, () => handleStyleChange(style.value))}
                        role="radio"
                        aria-checked={options.style === style.value}
                        aria-describedby={`${style.value}-description`}
                      >
                        {style.label}
                      </Button>
                    ))}
                  </div>
                </fieldset>
              )}
            </Field>

            <Field name="complexity" label="複雑さレベル" isRequired>
              {() => (
                <fieldset>
                  <legend style={{ marginBottom: token('space.100', '8px'), fontWeight: 500 }}>
                    複雑さレベルを選択してください
                  </legend>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr 1fr',
                      gap: token('space.100', '8px')
                    }}
                    role="radiogroup"
                    aria-labelledby="complexity-legend"
                  >
                    {COMPLEXITY_LEVELS.map((level) => (
                      <Button
                        key={level.value}
                        isSelected={options.complexity === level.value}
                        onClick={() => handleComplexityChange(level.value)}
                        onKeyDown={(e) => handleKeyDown(e, () => handleComplexityChange(level.value))}
                        role="radio"
                        aria-checked={options.complexity === level.value}
                      >
                        {level.label}
                      </Button>
                    ))}
                  </div>
                </fieldset>
              )}
            </Field>

            <Field name="colors" label="カラーパレット" isRequired>
              {() => (
                <fieldset>
                  <legend style={{ marginBottom: token('space.100', '8px'), fontWeight: 500 }}>
                    カラーパレットを選択してください（最大4色）
                  </legend>
                  <DraggableColorPalette
                    selectedColors={options.colors}
                    onColorsChange={(newColors) => onOptionChange('colors', newColors)}
                  />
                  <div style={{ marginTop: token('space.100', '8px'), fontSize: '0.875rem', color: token('color.text.subtle', '#44546F') }}>
                    選択された色: {options.colors.length}色
                  </div>
                </fieldset>
              )}
            </Field>

            <Field name="features" label="含める特徴">
              {() => (
                <fieldset>
                  <legend style={{ marginBottom: token('space.100', '8px'), fontWeight: 500 }}>
                    含める特徴を選択してください
                  </legend>
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: token('space.100', '8px')
                    }}
                    role="group"
                    aria-label="特徴選択"
                  >
                    {Object.entries(options.features).map(([feature, enabled]) => (
                      <Checkbox
                        key={feature}
                        isChecked={enabled}
                        onChange={(e) => handleFeatureChange(feature as keyof GenerationOptions['features'], e.target.checked)}
                        label={FEATURE_LABELS[feature as keyof typeof FEATURE_LABELS]}
                        name={feature}
                      />
                    ))}
                  </div>
                </fieldset>
              )}
            </Field>

            <FormFooter>
              <Button
                type="submit"
                appearance="primary"
                isLoading={isGenerating}
                iconBefore={isGenerating ? <RefreshIcon label="loading" /> : <EmojiObjectsIcon label="generate" />}
                isDisabled={!validation.isValid}
                aria-describedby="generate-description"
              >
                {isGenerating ? '生成中...' : 'アバターを生成'}
              </Button>
              <div id="generate-description" style={{ display: 'none' }}>
                選択されたオプションでAIアバターを生成します
              </div>
            </FormFooter>
          </form>
        )}
      </Form>
    </div>
  );
});

AvatarOptionsPanel.displayName = 'AvatarOptionsPanel';
