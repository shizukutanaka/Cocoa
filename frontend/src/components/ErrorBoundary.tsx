import React, { Component, ReactNode } from 'react';
import Button from '@atlaskit/button/standard-button';
import { token } from '@atlaskit/tokens';
import ErrorIcon from '@atlaskit/icon/glyph/error';
import RefreshIcon from '@atlaskit/icon/glyph/refresh';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  retryCount: number;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState(prevState => ({
      hasError: false,
      error: undefined,
      retryCount: prevState.retryCount + 1
    }));
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: token('space.400', '32px'),
            textAlign: 'center',
            backgroundColor: token('color.background.danger', '#FFEBE6'),
            borderRadius: '3px',
            border: `1px solid ${token('color.border.danger', '#DE350B')}`
          }}
          role="alert"
          aria-live="assertive"
        >
          <ErrorIcon
            label="error"
            primaryColor={token('color.icon.danger', '#DE350B')}
            size="large"
          />
          <h2
            style={{
              fontSize: '1.4rem',
              fontWeight: 500,
              marginTop: token('space.200', '16px'),
              marginBottom: token('space.100', '8px'),
              color: token('color.text.danger', '#DE350B')
            }}
          >
            エラーが発生しました
          </h2>
          <p
            style={{
              color: token('color.text.subtle', '#44546F'),
              marginBottom: token('space.200', '16px')
            }}
          >
            アバター生成で予期しないエラーが発生しました。再度お試しください。
            {this.state.retryCount > 0 && (
              <span>（試行回数: {this.state.retryCount}）</span>
            )}
          </p>
          <div style={{ display: 'flex', gap: token('space.100', '8px') }}>
            <Button
              onClick={this.handleRetry}
              appearance="primary"
              iconBefore={<RefreshIcon label="retry" />}
            >
              再試行
            </Button>
            <Button
              onClick={this.handleReload}
              appearance="subtle"
            >
              ページ再読み込み
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
