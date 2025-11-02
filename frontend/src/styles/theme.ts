import { token } from '@atlaskit/tokens';

/**
 * Defines the custom theme for the Cocoa application.
 * This theme overrides the default Atlassian design tokens to provide a unique brand identity.
 */
export const cocoaTheme = {
  // Example of overriding brand colors.
  // We'll use shades of brown to align with the "Cocoa" name.
  'color.background.brand.bold': token('color.background.brand.bold', '#5C4033'), // A dark brown for primary actions
  'color.text.brand': token('color.text.brand', '#5C4033'),
  'color.border.brand': token('color.border.brand', '#5C4033'),

  'color.background.brand.bold.hovered': token('color.background.brand.bold.hovered', '#7C5846'),
  'color.background.brand.bold.pressed': token('color.background.brand.bold.pressed', '#4C3023'),
};

/**
 * Dark theme variant for Cocoa application.
 */
export const cocoaDarkTheme = {
  'color.background.brand.bold': token('color.background.brand.bold', '#8B4513'), // Lighter brown for dark mode
  'color.text.brand': token('color.text.brand', '#D2B48C'),
  'color.border.brand': token('color.border.brand', '#8B4513'),

  'color.background.brand.bold.hovered': token('color.background.brand.bold.hovered', '#A0522D'),
  'color.background.brand.bold.pressed': token('color.background.brand.bold.pressed', '#654321'),

  // Dark mode specific colors
  'color.background.default': token('color.background.default', '#1a1a1a'),
  'color.text.default': token('color.text.default', '#ffffff'),
  'color.background.subtle': token('color.background.subtle', '#2d2d2d'),
  'color.border.default': token('color.border.default', '#404040'),
};

export type ThemeMode = 'light' | 'dark';

export const getTheme = (mode: ThemeMode) => {
  return mode === 'dark' ? cocoaDarkTheme : cocoaTheme;
};
