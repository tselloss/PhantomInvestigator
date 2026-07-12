import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./App.css";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Terms from "./pages/Terms";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import Investigate from "./pages/Investigate";
import Investigations from "./pages/Investigations";
import InvestigationDetail from "./pages/InvestigationDetail";
import Clients from "./pages/Clients";
import Runbooks from "./pages/Runbooks";
import Integrations from "./pages/Integrations";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";

function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/terms" element={<Terms />} />
              <Route element={<RequireAuth />}>
                <Route element={<Layout />}>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/investigate" element={<Investigate />} />
                  <Route path="/investigations" element={<Investigations />} />
                  <Route path="/investigations/:id" element={<InvestigationDetail />} />
                  <Route path="/clients" element={<Clients />} />
                  <Route path="/runbooks" element={<Runbooks />} />
                  <Route path="/settings/profile" element={<Profile />} />
                  <Route path="/settings/integrations" element={<Integrations />} />
                </Route>
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </ErrorBoundary>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}

export default App;
