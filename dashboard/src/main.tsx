import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { ThemeProvider } from "./shared/theme";
import { SelectedRunProvider } from "./shared/selectedRun";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1500,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <SelectedRunProvider>
          <App />
        </SelectedRunProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
