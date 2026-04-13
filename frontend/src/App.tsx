import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RootLayout } from "@/components/layout/root-layout";
import PipelinePage from "@/pages/pipeline";
import LeadsPage from "@/pages/leads";
import LeadDetailPage from "@/pages/lead-detail";
import EmailPage from "@/pages/email";
import ExportPage from "@/pages/export";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RootLayout>
          <Routes>
            <Route path="/" element={<LeadsPage />} />
            <Route path="/leads/:id" element={<LeadDetailPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/email" element={<EmailPage />} />
            <Route path="/export" element={<ExportPage />} />
          </Routes>
        </RootLayout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
