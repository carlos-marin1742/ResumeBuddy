import { useEffect, useState } from "react";

async function api(path, options = {}) {
  const response = await fetch(`/api/auth${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed.");
  return body;
}

export default function AuthGate({ children }) {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    const isVerify = window.location.pathname === "/verify-email";
    if (token && isVerify) {
      api("/verify-email", { method: "POST", body: JSON.stringify({ token }) })
        .then((data) => setMessage(data.detail)).catch((error) => setMessage(error.message)).finally(() => setReady(true));
      return;
    }
    api("/me").then(() => setSignedIn(true)).catch(() => {}).finally(() => setReady(true));
  }, []);

  if (!ready) return <main className="app"><p>Checking your session…</p></main>;
  if (signedIn) return children;
  async function submit(event) {
    event.preventDefault(); setMessage("");
    try {
      const result = await api(registering ? "/register" : "/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setMessage(result.detail);
      if (!registering) setSignedIn(true);
    } catch (error) { setMessage(error.message); }
  }
  return <main className="app"><section className="card" style={{ maxWidth: 440, margin: "4rem auto" }}>
    <h1>{registering ? "Create your account" : "Sign in"}</h1>
    <p>Resume data is available only after your email is verified.</p>
    <form onSubmit={submit}>
      <label>Email<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <label>Password<input type="password" autoComplete={registering ? "new-password" : "current-password"} minLength="12" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      <button className="btn btn-primary" type="submit">{registering ? "Create account" : "Sign in"}</button>
    </form>
    {message && <p role="status">{message}</p>}
    <button className="btn btn-secondary" type="button" onClick={() => { setRegistering(!registering); setMessage(""); }}>{registering ? "Already have an account? Sign in" : "Need an account? Register"}</button>
  </section></main>;
}
