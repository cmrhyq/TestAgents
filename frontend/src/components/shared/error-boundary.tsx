import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full min-h-[400px] flex-col items-center justify-center gap-4 p-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-6 w-6 text-destructive" />
          </div>
          <div className="text-center">
            <h2 className="text-lg font-semibold text-foreground">出错了</h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              {this.state.error?.message || "发生了未知错误。"}
            </p>
          </div>
          <button
            type="button"
            onClick={this.handleReset}
            className="inline-flex items-center gap-2 rounded-md border-0 bg-card px-4 py-2 text-sm font-medium text-foreground shadow-card transition-colors hover:bg-secondary"
          >
            <RefreshCw className="h-4 w-4" />
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
