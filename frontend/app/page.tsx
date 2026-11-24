"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CopilotKit, CopilotChat } from "@copilotkit/react-core/v2";

interface UserProfile {
  user_id: string;
  nombre: string;
  rol: "empleado" | "gerente" | "director";
  limite_aprobacion: number;
}

interface AuthSession {
  token: string;
  user: UserProfile;
}

const STORAGE_KEY = "expense_approval_auth_session";

export default function HomePage() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [rol, setRol] = useState<"empleado" | "gerente" | "director">("empleado");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setSession(JSON.parse(saved) as AuthSession);
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    } finally {
      setHydrated(true);
    }
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const payload =
        mode === "login"
          ? { email, password }
          : { email, password, nombre, rol };

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "No se pudo completar la autenticación.");
        return;
      }

      const nextSession: AuthSession = {
        token: data.access_token,
        user: data.user,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSession));
      setSession(nextSession);
      setPassword("");
    } catch {
      setError("Error de red intentando conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setError(null);
  }

  const copilotHeaders = useMemo(
    () =>
      session
        ? { Authorization: `Bearer ${session.token}` }
        : undefined,
    [session],
  );

  if (!hydrated) {
    return null;
  }

  if (!session) {
    return (
      <main className="auth-shell">
        <div className="auth-card">
          <h1 className="auth-title">Expense Approval Agent</h1>
          <p className="auth-subtitle">
            Google ADK 2.0 + AG-UI + Autenticación JWT multi-usuario
          </p>

          <div className="auth-tabs">
            <button
              type="button"
              className={mode === "login" ? "tab active" : "tab"}
              onClick={() => {
                setMode("login");
                setError(null);
              }}
            >
              Iniciar sesión
            </button>
            <button
              type="button"
              className={mode === "register" ? "tab active" : "tab"}
              onClick={() => {
                setMode("register");
                setError(null);
              }}
            >
              Crear cuenta
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "register" && (
              <>
                <label className="field">
                  <span>Nombre completo</span>
                  <input
                    type="text"
                    required
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="Ej: Laura Martínez"
                  />
                </label>

                <label className="field">
                  <span>Rol (define tu límite automático)</span>
                  <select
                    value={rol}
                    onChange={(e) =>
                      setRol(e.target.value as "empleado" | "gerente" | "director")
                    }
                  >
                    <option value="empleado">Empleado (auto &lt;= 1,000)</option>
                    <option value="gerente">Gerente (auto &lt;= 5,000)</option>
                    <option value="director">Director (auto &lt;= 15,000)</option>
                  </select>
                </label>
              </>
            )}

            <label className="field">
              <span>Correo electrónico</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ana@empresa.com"
              />
            </label>

            <label className="field">
              <span>Contraseña</span>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Mínimo 6 caracteres"
              />
            </label>

            {error && <p className="auth-error">{error}</p>}

            <button className="primary-btn" type="submit" disabled={loading}>
              {loading
                ? "Procesando..."
                : mode === "login"
                  ? "Entrar"
                  : "Registrarme y entrar"}
            </button>
          </form>

          {mode === "login" && (
            <div className="demo-hint">
              <strong>Usuarios de prueba precargados (clave: demo1234):</strong>
              <div>• ana@empresa.com (Empleado · límite &lt;= 1,000)</div>
              <div>• carlos@empresa.com (Gerente · límite &lt;= 5,000)</div>
            </div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="app-title">Expense Approval Agent</h1>
          <p className="app-subtitle">
            {session.user.nombre} ({session.user.user_id})
          </p>
        </div>

        <div className="user-bar">
          <span className="role-badge">
            {session.user.rol.toUpperCase()} · límite &lt;={" "}
            {session.user.limite_aprobacion.toLocaleString()}
          </span>
          <button
            type="button"
            className="logout-btn"
            onClick={handleLogout}
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <section className="chat-container">
        <CopilotKit
          key={session.user.user_id}
          runtimeUrl="/api/copilotkit"
          agent="expense_approval_agent"
          headers={copilotHeaders}
        >
          <CopilotChat
            labels={{
              chatInputPlaceholder:
                "Ej: Factura de licencias JetBrains por 250 USD, o Contrato cloud por 4500 USD...",
            }}
          />
        </CopilotKit>
      </section>
    </main>
  );
}
