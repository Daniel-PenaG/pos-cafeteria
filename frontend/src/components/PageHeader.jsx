export default function PageHeader({ title, subtitle, children }) {
  return (
    <header className="page-header">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
        </div>
        {children}
      </div>
    </header>
  );
}
