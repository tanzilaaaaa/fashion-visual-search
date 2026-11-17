import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, imageSrc, toApiError } from "../api/client";
import { AlertIcon, ArrowRightIcon, EyeIcon, EyeOffIcon, HangerIcon } from "../components/Icons";
import { Logo } from "../components/Logo";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { useAuth } from "../context/AuthContext";
import { useAsync } from "../hooks/useAsync";
import { altText } from "../lib/format";

type Mode = "signin" | "signup";
type Field = "name" | "email" | "password";

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;

/** Mirrors the API's password policy so most problems are caught before submitting. */
export function passwordProblem(pw: string): string | null {
  if (pw.length < 8) return "Use at least 8 characters.";
  if (pw.length > 128) return "Use at most 128 characters.";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Include at least one letter and one number.";
  return null;
}

/** 0–4 strength score for the meter (length, mixed case, digits, symbols). */
export function passwordStrength(pw: string): number {
  if (!pw) return 0;
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(4, Math.max(passwordProblem(pw) ? 1 : 2, s));
}

const STRENGTH = ["", "Weak", "Fair", "Good", "Strong"];

function TextField({
  id, label, type = "text", value, onChange, error, autoComplete, hint, trailing,
}: {
  id: string; label: string; type?: string; value: string; onChange: (v: string) => void;
  error?: string | null; autoComplete: string; hint?: ReactNode; trailing?: ReactNode;
}) {
  const errId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      <div className="relative">
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          aria-invalid={!!error}
          aria-describedby={[error ? errId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined}
          className={`input ${trailing ? "pr-12" : ""} ${error ? "border-danger focus:border-danger focus:ring-danger/15" : ""}`}
        />
        {trailing}
      </div>
      {error ? (
        <p id={errId} className="mt-1.5 text-sm text-danger">{error}</p>
      ) : hint ? (
        <div id={hintId} className="mt-1.5">{hint}</div>
      ) : null}
    </div>
  );
}

function SidePanel({ mode }: { mode: Mode }) {
  const showcase = useAsync(() => api.showcase(6), []);
  const items = showcase.data?.items ?? [];
  return (
    <aside className="bg-gradient-accent relative hidden overflow-hidden p-10 text-on-accent lg:flex lg:flex-col">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-20" aria-hidden="true" />
      <div className="relative">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] opacity-80">Lookbook</p>
        <h2 className="mt-4 max-w-md font-display text-4xl font-semibold leading-tight">
          {mode === "signup" ? "Your personal fashion search engine." : "Welcome back. Your next find is a sentence away."}
        </h2>
        <p className="mt-4 max-w-md opacity-90">
          Search ~50,000 DeepFashion2 garments by description or by photo, then explore similar pieces and complete the look.
        </p>
      </div>
      <div className="relative mt-10 grid flex-1 grid-cols-3 content-end gap-3">
        {(items.length ? items : Array.from({ length: 6 }, () => null)).map((it, i) => (
          <div
            key={it?.item_id ?? i}
            className="aspect-[3/4] overflow-hidden rounded-2xl bg-canvas/90 shadow-lift animate-float"
            style={{ animationDelay: `${i * 0.4}s`, transform: i % 2 ? "translateY(18px)" : undefined }}
          >
            {it ? (
              <img src={imageSrc(it.image_url)} alt={altText(it)} className="h-full w-full object-cover" />
            ) : (
              <div className="grid h-full place-items-center text-ink-muted"><HangerIcon /></div>
            )}
          </div>
        ))}
      </div>
      <p className="relative mt-8 text-sm opacity-80">
        CLIP ViT-B/32 · fine-tuned adapter · FAISS — Polaris School of Technology OJT
      </p>
    </aside>
  );
}

export function AuthPage({ mode }: { mode: Mode }) {
  const { allowed, checking, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/app";
  const uid = useId();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<ReactNode>(null);
  const [busy, setBusy] = useState(false);

  if (!checking && allowed) return <Navigate to={from} replace />;

  const signup = mode === "signup";
  const strength = passwordStrength(password);

  const validate = () => {
    const next: Partial<Record<Field, string>> = {};
    if (signup && !name.trim()) next.name = "Please enter your name.";
    if (!EMAIL_RE.test(email.trim())) next.email = "Enter a valid email address.";
    if (signup) {
      const p = passwordProblem(password);
      if (p) next.password = p;
    } else if (!password) next.password = "Enter your password.";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setBusy(true);
    try {
      if (signup) await register(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      const e2 = toApiError(err);
      if (e2.code === "email_taken") {
        setErrors({ email: "An account with this email already exists." });
        setFormError(<>Already registered? <Link to="/signin" state={{ from }} className="font-semibold underline">Sign in instead</Link>.</>);
      } else if (e2.code === "weak_password") setErrors({ password: e2.message });
      else if (e2.code === "invalid_email") setErrors({ email: e2.message });
      else if (e2.code === "invalid_name") setErrors({ name: e2.message });
      else setFormError(e2.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <SidePanel mode={mode} />
      <div className="relative flex flex-col">
        <div className="bg-mesh pointer-events-none absolute inset-0 lg:hidden" aria-hidden="true" />
        <div className="relative flex items-center justify-between px-4 py-5 sm:px-8">
          <Logo />
          <ThemeSwitcher compact />
        </div>
        <main id="main" className="relative flex flex-1 items-center justify-center px-4 pb-16 sm:px-8">
          <div className="w-full max-w-md animate-fade-up">
            <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
              {signup ? "Create your account" : "Sign in"}
            </h1>
            <p className="mt-2 text-ink-soft">
              {signup ? "Free, and it takes ten seconds." : "Good to see you again."}{" "}
              {signup ? "Already have an account? " : "New to Lookbook? "}
              <Link to={signup ? "/signin" : "/signup"} state={{ from }} className="font-semibold text-accent hover:underline">
                {signup ? "Sign in" : "Create an account"}
              </Link>
            </p>

            <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
              {signup && (
                <TextField id={`${uid}-name`} label="Full name" value={name} onChange={setName} error={errors.name} autoComplete="name" />
              )}
              <TextField id={`${uid}-email`} label="Email" type="email" value={email} onChange={setEmail} error={errors.email} autoComplete="email" />
              <TextField
                id={`${uid}-password`}
                label="Password"
                type={show ? "text" : "password"}
                value={password}
                onChange={setPassword}
                error={errors.password}
                autoComplete={signup ? "new-password" : "current-password"}
                trailing={
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Hide password" : "Show password"}
                    aria-pressed={show}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-ink-muted hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    {show ? <EyeOffIcon width={18} height={18} /> : <EyeIcon width={18} height={18} />}
                  </button>
                }
                hint={
                  signup ? (
                    <div aria-live="polite">
                      <div className="flex gap-1" aria-hidden="true">
                        {[1, 2, 3, 4].map((i) => (
                          <span key={i} className={`h-1.5 flex-1 rounded-full transition ${i <= strength ? (strength <= 1 ? "bg-danger" : strength === 2 ? "bg-accent-2" : "bg-success") : "bg-surface-2"}`} />
                        ))}
                      </div>
                      <p className="mt-1.5 text-xs text-ink-muted">
                        {password ? `Strength: ${STRENGTH[strength]}. ` : ""}At least 8 characters with a letter and a number.
                      </p>
                    </div>
                  ) : undefined
                }
              />

              {formError && (
                <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
                  <AlertIcon width={18} height={18} className="mt-0.5 shrink-0" />
                  <div>{formError}</div>
                </div>
              )}

              <button type="submit" disabled={busy} className="btn-primary w-full py-3 text-base">
                {busy ? (
                  <><span className="h-4 w-4 animate-spin rounded-full border-2 border-on-accent/40 border-t-on-accent" /> {signup ? "Creating account…" : "Signing in…"}</>
                ) : (
                  <>{signup ? "Create account" : "Sign in"} <ArrowRightIcon width={18} height={18} /></>
                )}
              </button>
              <p className="text-center text-xs text-ink-muted">
                Passwords are stored as salted scrypt hashes. Your uploaded photos are never stored.
              </p>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}
