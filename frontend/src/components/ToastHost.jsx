import { useToastStore } from "../store/toastStore";

export default function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (!toasts.length) return null;

  return (
    <div className="toast-host" aria-live="polite" aria-relevant="additions">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast toast--${t.variant}`}
          role={t.variant === "error" ? "alert" : "status"}
        >
          <span className="toast__message">{t.message}</span>
          <button
            type="button"
            className="toast__close"
            aria-label="Cerrar aviso"
            onClick={() => dismiss(t.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
