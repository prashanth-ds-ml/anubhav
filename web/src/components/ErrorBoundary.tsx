import { Component, type ErrorInfo, type ReactNode } from "react";

// If one part of the page fails to render, only that part shows a message; the header, the tabs and the rest of the
// page keep working (Nov 4: a draft with an unexpected shape blanked the whole app). `resetKey` lets the part try again
// when what it shows changes (another tab, new data).
export class ErrorBoundary extends Component<{ name: string; resetKey?: unknown; children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.name}] could not be shown`, error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: unknown }) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="panel boundary" role="alert">
        <p><strong>{this.props.name} could not be shown.</strong> The rest of the page still works.</p>
        <p className="small muted">{this.state.error.message}</p>
        <button type="button" className="chip" onClick={() => this.setState({ error: null })}>Try again</button>
      </div>
    );
  }
}
