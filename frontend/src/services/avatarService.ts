import { apiClient } from '@/services/apiClient';
import { GenerationOptions, GeneratedAvatar, GenerationHistoryItem } from '@/types/avatarTypes';

export interface AvatarSummary {
  readonly id: string;
  readonly name: string;
  readonly creator: string;
  readonly createdAt: string;
  readonly status: 'active' | 'inactive' | 'archived';
}

export interface AvatarListResponse {
  readonly items: AvatarSummary[];
}

export interface GenerateAvatarRequest {
  options: GenerationOptions;
  user_id: string;
}

export interface GenerateAvatarResponse {
  success: boolean;
  avatar?: GeneratedAvatar;
  error?: string;
}

export interface DownloadAvatarRequest {
  avatar_id: string;
}

export const fetchAvatars = async (): Promise<AvatarSummary[]> => {
  const { data } = await apiClient.get<AvatarListResponse>('/avatars');
  return data.items;
};

export const generateAvatar = async (request: GenerateAvatarRequest): Promise<GenerateAvatarResponse> => {
  try {
    const { data } = await apiClient.post<GenerateAvatarResponse>('/api/v1/ai/generate-avatar', request);
    return data;
  } catch (error) {
    console.error('Avatar generation error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : '生成に失敗しました。'
    };
  }
};

export const downloadAvatar = async (request: DownloadAvatarRequest): Promise<Blob> => {
  const { data } = await apiClient.post('/api/v1/avatars/download', request, {
    responseType: 'blob'
  });
  return data;
};

export const fetchGenerationHistory = async (userId: string): Promise<GenerationHistoryItem[]> => {
  try {
    const { data } = await apiClient.get<{ history: GenerationHistoryItem[] }>(`/api/v1/users/${userId}/avatar-history`);
    return data.history;
  } catch (error) {
    console.error('Failed to fetch generation history:', error);
    return [];
  }
};

export const saveGenerationHistory = async (historyItem: GenerationHistoryItem): Promise<void> => {
  try {
    await apiClient.post('/api/v1/avatar-history', historyItem);
  } catch (error) {
    console.error('Failed to save generation history:', error);
  }
};
