export default function OperationalConfirmModal({
  open,
  title = "Confirmar",
  message,
  confirmLabel = "Continuar",
  cancelLabel = "Cancelar",
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onCancel} role="presentation">
      <div
        className="modal-box"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="oper-confirm-title"
      >
        <h2 id="oper-confirm-title">{title}</h2>
        <p style={{ whiteSpace: "pre-wrap" }}>{message}</p>
        <div className="btn-group" style={{ marginTop: "1.25rem", display: "flex", gap: "0.5rem" }}>
          <button type="button" className="btn btn--secondary" style={{ flex: 1 }} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="btn btn--accent" style={{ flex: 1 }} onClick={onConfirm} autoFocus>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
