import { GenerationOptions } from '@/types/avatarTypes';

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

export const validateAvatarOptions = (options: GenerationOptions): ValidationResult => {
  const errors: string[] = [];

  // スタイルの検証
  if (!options.style) {
    errors.push('アバタースタイルを選択してください');
  }

  // 複雑さレベルの検証
  if (!options.complexity) {
    errors.push('複雑さレベルを選択してください');
  }

  // カラーパレットの検証
  if (options.colors.length === 0) {
    errors.push('少なくとも1色を選択してください');
  }

  if (options.colors.length > 4) {
    errors.push('カラーは最大4色まで選択できます');
  }

  // 特徴の検証（オプションなので警告程度）
  const enabledFeatures = Object.values(options.features).filter(Boolean).length;
  if (enabledFeatures === 0) {
    errors.push('少なくとも1つの特徴を選択することをおすすめします');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
};

export const validateColor = (color: string): boolean => {
  const colorRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
  return colorRegex.test(color);
};

export const sanitizeOptions = (options: GenerationOptions): GenerationOptions => {
  return {
    ...options,
    colors: options.colors.filter(validateColor).slice(0, 4),
    style: options.style || 'realistic',
    complexity: options.complexity || 'moderate'
  };
};
