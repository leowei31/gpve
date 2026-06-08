import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Discover from "./pages/Discover";
import Collections from "./pages/Collections";
import Insights from "./pages/Insights";
import GameDetail from "./pages/GameDetail";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Discover />} />
        <Route path="collections" element={<Collections />} />
        <Route path="insights" element={<Insights />} />
        <Route path="game/:id" element={<GameDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
