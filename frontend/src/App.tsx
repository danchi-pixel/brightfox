import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Tooltip } from "radix-ui";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { ConfirmProvider } from "@/components/ui/confirm";
import { AuthGate, useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import ExamPage from "@/features/learner/ExamPage";
import LearnerHome from "@/features/learner/LearnerHome";
import ReviewPage from "@/features/learner/ReviewPage";
import LearnPage from "@/features/learner/LearnPage";
import MockPage from "@/features/learner/MockPage";
import OralPage from "@/features/learner/OralPage";
import PracticePage from "@/features/learner/PracticePage";
import VideoPage from "@/features/learner/VideoPage";
import FamilyPage from "@/features/parent/FamilyPage";
import OverviewPage from "@/features/parent/OverviewPage";
import FoxyPage from "@/features/parent/FoxyPage";
import GuidePage from "@/features/parent/GuidePage";
import TestsPage from "@/features/parent/TestsPage";
import TopicsPage from "@/features/parent/TopicsPage";
import ChatPage from "@/features/tutor/ChatPage";

/** Parents' pages (the server refuses them for learners anyway). */
function ParentOnly({ children }: { children: React.ReactNode }) {
  const { isAdmin, ownLearnerId } = useAuth();
  return isAdmin ? children : <Navigate to={`/l/${ownLearnerId}`} replace />;
}

/** "/" is the overview for parents and the classroom for a learner. */
function Home() {
  const { isAdmin, ownLearnerId } = useAuth();
  return isAdmin ? <OverviewPage /> : <Navigate to={`/l/${ownLearnerId}`} replace />;
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: true } },
});

const router = createBrowserRouter([
  {
    element: (
      <ConfirmProvider>
        <AppShell />
      </ConfirmProvider>
    ),
    children: [
      { path: "/", element: <Home /> },
      { path: "/topics", element: <ParentOnly><TopicsPage /></ParentOnly> },
      { path: "/foxy", element: <ParentOnly><FoxyPage /></ParentOnly> },
      { path: "/tests", element: <ParentOnly><TestsPage /></ParentOnly> },
      { path: "/family", element: <ParentOnly><FamilyPage /></ParentOnly> },
      { path: "/guide", element: <ParentOnly><GuidePage /></ParentOnly> },
      { path: "/l/:lid", element: <LearnerHome /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
  // Full-screen pages: one thing at a time.
  { path: "/l/:lid/learn/:tid", element: <LearnPage /> },
  { path: "/l/:lid/practice/:tid", element: <PracticePage /> },
  { path: "/l/:lid/chat/:cid", element: <ChatPage /> },
  { path: "/l/:lid/exam/:eid", element: <ExamPage /> },
  { path: "/l/:lid/review", element: <ReviewPage /> },
  { path: "/l/:lid/mock/:mid", element: <MockPage /> },
  { path: "/l/:lid/oral/:tid", element: <OralPage /> },
  { path: "/l/:lid/video/:tid", element: <VideoPage /> },
  { path: "/preview/:tid/video", element: <ParentOnly><VideoPage /></ParentOnly> },
  { path: "/preview-mock/:mid", element: <ParentOnly><MockPage /></ParentOnly> },
  { path: "/preview/:tid", element: <ParentOnly><PracticePage /></ParentOnly> },
  { path: "/preview/:tid/learn", element: <ParentOnly><LearnPage /></ParentOnly> },
]);

export default function App() {
  const { theme } = useTheme();
  return (
    <QueryClientProvider client={queryClient}>
      <Tooltip.Provider>
        <AuthGate>
          <RouterProvider router={router} />
        </AuthGate>
        <Toaster theme={theme} position="top-center" richColors closeButton toastOptions={{ duration: 3500 }} />
      </Tooltip.Provider>
    </QueryClientProvider>
  );
}
