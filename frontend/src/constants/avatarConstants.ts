export const AVATAR_STYLES = [
  { value: 'realistic', label: 'リアル' },
  { value: 'anime', label: 'アニメ' },
  { value: 'cartoon', label: 'カートゥーン' },
  { value: 'minimalist', label: 'ミニマリスト' },
  { value: 'vr-ready', label: 'VR対応' },
  { value: 'nft-compatible', label: 'NFT対応' },
  { value: 'metaverse-optimized', label: 'メタバース最適化' }
] as const;

export const COMPLEXITY_LEVELS = [
  { value: 'simple', label: 'シンプル' },
  { value: 'moderate', label: '標準' },
  { value: 'complex', label: '複雑' },
  { value: 'high-performance', label: '高性能' },
  { value: 'ultra-detailed', label: '超詳細' }
] as const;

export const COLOR_PALETTE = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
  '#8B5CF6', '#EC4899', '#6B7280', '#000000'
] as const;

export const FEATURE_LABELS = {
  hair: '髪型',
  eyes: '目',
  mouth: '口',
  accessories: 'アクセサリー'
} as const;

export const DEFAULT_AVATAR_OPTIONS = {
  style: 'realistic' as const,
  complexity: 'moderate' as const,
  colors: ['#3B82F6', '#10B981', '#F59E0B'],
  features: {
    hair: true,
    eyes: true,
    mouth: true,
    accessories: false
  }
} as const;

export type AvatarStyle = typeof AVATAR_STYLES[number]['value'];
export type ComplexityLevel = typeof COMPLEXITY_LEVELS[number]['value'];
export type ColorPalette = typeof COLOR_PALETTE[number];
