import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error("ErrorBoundary caught:", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="empty-state">
          <p>予期しないエラーが発生しました。</p>
          <button className="btn btn-secondary" onClick={() => window.location.reload()}>
            ページを再読み込み
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
