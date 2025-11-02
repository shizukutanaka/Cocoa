import React, { useEffect, useState } from 'react';
import { token } from '@atlaskit/tokens';

interface NotificationToastProps {
  message: string;
  type?: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
  onClose?: () => void;
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  message,
  type = 'info',
  duration = 5000,
  onClose,
}) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      onClose?.();
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  if (!isVisible) return null;

  const typeStyles = {
    success: {
      backgroundColor: token('color.background.success', '#E3FCEF'),
      borderColor: token('color.border.success', '#00A86B'),
      color: token('color.text.success', '#006644'),
    },
    error: {
      backgroundColor: token('color.background.danger', '#FFEBE6'),
      borderColor: token('color.border.danger', '#DE350B'),
      color: token('color.text.danger', '#DE350B'),
    },
    warning: {
      backgroundColor: token('color.background.warning', '#FFF3CD'),
      borderColor: token('color.border.warning', '#FFC107'),
      color: token('color.text.warning', '#856404'),
    },
    info: {
      backgroundColor: token('color.background.information', '#E6F3FF'),
      borderColor: token('color.border.information', '#0052CC'),
      color: token('color.text.information', '#003884'),
    },
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: token('space.200', '16px'),
        right: token('space.200', '16px'),
        padding: token('space.200', '16px'),
        borderRadius: '4px',
        border: `1px solid`,
        maxWidth: '300px',
        boxShadow: token('elevation.shadow.raised', '0 1px 3px rgba(9, 30, 66, 0.13)'),
        zIndex: 1000,
        ...typeStyles[type],
      }}
      role="alert"
      aria-live="assertive"
    >
      <p style={{ margin: 0, fontSize: '0.875rem' }}>
        {message}
      </p>
      <button
        onClick={() => {
          setIsVisible(false);
          onClose?.();
        }}
        style={{
          position: 'absolute',
          top: '4px',
          right: '4px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '16px',
          color: 'inherit',
          opacity: 0.7,
        }}
        aria-label="通知を閉じる"
      >
        ×
      </button>
    </div>
  );
};
