import { useReducer, useCallback } from 'react';
import { apiClient } from '@/services/apiClient';
import { DEFAULT_AVATAR_OPTIONS } from '@/constants/avatarConstants';
import { GeneratedAvatar, GenerationHistoryItem, AvatarGenerationState, AvatarGenerationAction } from '@/types/avatarTypes';

const initialState: AvatarGenerationState = {
  isGenerating: false,
  generatedAvatar: null,
  history: [],
  options: DEFAULT_AVATAR_OPTIONS,
  error: null,
};

const avatarGenerationReducer = (state: AvatarGenerationState, action: AvatarGenerationAction): AvatarGenerationState => {
  switch (action.type) {
    case 'SET_GENERATING':
      return { ...state, isGenerating: action.payload };
    case 'SET_AVATAR':
      return { ...state, generatedAvatar: action.payload, error: null };
    case 'SET_HISTORY':
      return { ...state, history: action.payload };
    case 'ADD_TO_HISTORY':
      return {
        ...state,
        history: [action.payload, ...state.history.slice(0, 9)] // 最新10件保持
      };
    case 'SET_OPTION':
      return {
        ...state,
        options: {
          ...state.options,
          [action.payload.key]: action.payload.value
        }
      };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isGenerating: false };
    case 'RESET_ERROR':
      return { ...state, error: null };
    default:
      return state;
  }
};

export const useAvatarGeneration = () => {
  const [state, dispatch] = useReducer(avatarGenerationReducer, initialState);

  const generateAvatar = useCallback(async () => {
    dispatch({ type: 'SET_GENERATING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      const response = await apiClient.post<{ success: boolean; avatar: GeneratedAvatar }>('/api/v1/ai/generate-avatar', {
        options: state.options,
        user_id: 'current_user_id'
      });

      if (response.data.success) {
        const avatar = response.data.avatar;
        dispatch({ type: 'SET_AVATAR', payload: avatar });

        const historyItem: GenerationHistoryItem = {
          id: `history_${Date.now()}`,
          avatar,
          timestamp: new Date().toISOString(),
        };
        dispatch({ type: 'ADD_TO_HISTORY', payload: historyItem });
      } else {
        dispatch({ type: 'SET_ERROR', payload: '生成に失敗しました。再度お試しください。' });
      }
    } catch (error) {
      console.error('生成エラー:', error);
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : '予期しないエラーが発生しました。'
      });
    } finally {
      dispatch({ type: 'SET_GENERATING', payload: false });
    }
  }, [state.options]);

  const updateOption = useCallback((key: keyof typeof state.options, value: any) => {
    dispatch({ type: 'SET_OPTION', payload: { key, value } });
  }, []);

  const downloadAvatar = useCallback(async (avatar: GeneratedAvatar) => {
    try {
      const response = await apiClient.post('/api/v1/avatars/download', {
        avatar_id: avatar.id
      }, { responseType: 'blob' });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${avatar.name}.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('ダウンロードエラー:', error);
      dispatch({ type: 'SET_ERROR', payload: 'ダウンロードに失敗しました。' });
    }
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'RESET_ERROR' });
  }, []);

  return {
    state,
    dispatch,
    generateAvatar,
    updateOption,
    downloadAvatar,
    clearError,
  };
};
