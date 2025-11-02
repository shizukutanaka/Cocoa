import { useCallback } from 'react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { DEFAULT_AVATAR_OPTIONS } from '@/constants/avatarConstants';
import { GenerationOptions } from '@/types/avatarTypes';

export const useAvatarOptions = () => {
  const [options, setOptions] = useLocalStorage<GenerationOptions>('avatar_generation_options', DEFAULT_AVATAR_OPTIONS);

  const updateOption = useCallback(<K extends keyof GenerationOptions>(
    key: K,
    value: GenerationOptions[K]
  ) => {
    setOptions(prev => ({
      ...prev,
      [key]: value
    }));
  }, [setOptions]);

  const updateFeature = useCallback((feature: keyof GenerationOptions['features'], enabled: boolean) => {
    setOptions(prev => ({
      ...prev,
      features: {
        ...prev.features,
        [feature]: enabled
      }
    }));
  }, [setOptions]);

  const updateColors = useCallback((colors: string[]) => {
    setOptions(prev => ({
      ...prev,
      colors: colors.slice(0, 4) as GenerationOptions['colors']
    }));
  }, [setOptions]);

  const resetOptions = useCallback(() => {
    setOptions(DEFAULT_AVATAR_OPTIONS);
  }, [setOptions]);

  const toggleColor = useCallback((color: string) => {
    setOptions(prev => {
      const newColors = prev.colors.includes(color as any)
        ? prev.colors.filter(c => c !== color)
        : [...prev.colors, color];
      return {
        ...prev,
        colors: newColors.slice(0, 4) as GenerationOptions['colors']
      };
    });
  }, [setOptions]);

  return {
    options,
    updateOption,
    updateFeature,
    updateColors,
    resetOptions,
    toggleColor,
  };
};
