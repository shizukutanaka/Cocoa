import React from 'react';
import ReactDOM from 'react-dom/client';
import '@atlaskit/css-reset';
import { setGlobalTheme } from '@atlaskit/tokens';
import { cocoaTheme } from './styles/theme';
import App from './App.tsx';

// Apply the custom theme globally
setGlobalTheme({ colorMode: 'light', ...cocoaTheme });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
