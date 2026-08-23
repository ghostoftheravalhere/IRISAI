import React from "react";

/**
 * Top-Level React ErrorBoundary Component
 * Prevents silent blank/black screens by displaying an interactive recovery & diagnostics panel.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDiagnostics: false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("[REACT ERROR BOUNDARY]", error, errorInfo);
    this.setState({ errorInfo });
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            backgroundColor: "#0a0a0f",
            color: "#f3f4f6",
            fontFamily: "system-ui, -apple-system, sans-serif",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <div
            style={{
              background: "#12131c",
              border: "1px solid #ef4444",
              borderRadius: "16px",
              padding: "2.5rem",
              maxWidth: "550px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(239,68,68,0.15)",
            }}
          >
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "50%",
                background: "rgba(239,68,68,0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.75rem",
                color: "#ef4444",
                margin: "0 auto 1.25rem auto",
              }}
            >
              ⚠️
            </div>

            <h1 style={{ fontSize: "1.5rem", fontWeight: "600", color: "#f87171", marginBottom: "0.5rem" }}>
              IRIS Interface Failed to Initialize
            </h1>

            <p style={{ color: "#9ca3af", fontSize: "0.95rem", lineHeight: "1.5", marginBottom: "1.5rem" }}>
              The presentation layer encountered a runtime exception. You can retry initialization or inspect diagnostic details below.
            </p>

            <div style={{ display: "flex", justifyContent: "center", gap: "1rem", marginBottom: "1.5rem" }}>
              <button
                onClick={this.handleRetry}
                style={{
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "0.75rem 1.5rem",
                  fontWeight: "600",
                  cursor: "pointer",
                }}
              >
                🔄 Retry Initialization
              </button>
              <button
                onClick={() => this.setState((prev) => ({ showDiagnostics: !prev.showDiagnostics }))}
                style={{
                  backgroundColor: "transparent",
                  border: "1px solid #4b5563",
                  color: "#e5e7eb",
                  borderRadius: "8px",
                  padding: "0.75rem 1.25rem",
                  fontWeight: "500",
                  cursor: "pointer",
                }}
              >
                ⚙ {this.state.showDiagnostics ? "Hide Diagnostics" : "Open Diagnostics"}
              </button>
            </div>

            {this.state.showDiagnostics && (
              <div
                style={{
                  textAlign: "left",
                  background: "#08090e",
                  border: "1px solid #27273a",
                  borderRadius: "8px",
                  padding: "1rem",
                  maxHeight: "200px",
                  overflowY: "auto",
                  fontSize: "0.85rem",
                  fontFamily: "monospace",
                  color: "#ef4444",
                }}
              >
                <div><strong>Error:</strong> {this.state.error?.toString()}</div>
                {this.state.errorInfo && (
                  <pre style={{ marginTop: "0.5rem", color: "#9ca3af", whiteSpace: "pre-wrap" }}>
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
