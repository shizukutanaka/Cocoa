import { AvatarStyle, ComplexityLevel, ColorPalette } from '@/constants/avatarConstants';

export interface GenerationOptions {
  style: AvatarStyle;
  complexity: ComplexityLevel;
  colors: ColorPalette[];
  features: {
    hair: boolean;
    eyes: boolean;
    mouth: boolean;
    accessories: boolean;
  };
}

export interface GeneratedAvatar {
  id: string;
  name: string;
  imageUrl: string;
  options: GenerationOptions;
  createdAt: string;
}

export interface GenerationHistoryItem {
  id: string;
  avatar: GeneratedAvatar;
  timestamp: string;
}

export interface AvatarGenerationState {
  isGenerating: boolean;
  generatedAvatar: GeneratedAvatar | null;
  history: GenerationHistoryItem[];
  options: GenerationOptions;
  error: string | null;
}

export type AvatarGenerationAction =
  | { type: 'SET_GENERATING'; payload: boolean }
  | { type: 'SET_AVATAR'; payload: GeneratedAvatar | null }
  | { type: 'SET_HISTORY'; payload: GenerationHistoryItem[] }
  | { type: 'ADD_TO_HISTORY'; payload: GenerationHistoryItem }
  | { type: 'SET_OPTION'; payload: { key: keyof GenerationOptions; value: any } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESET_ERROR' };

export interface UseAvatarGenerationReturn {
  state: AvatarGenerationState;
  dispatch: (action: AvatarGenerationAction) => void;
  generateAvatar: () => Promise<void>;
  updateOption: (key: keyof GenerationOptions, value: any) => void;
  downloadAvatar: (avatar: GeneratedAvatar) => void;
  clearError: () => void;
}
