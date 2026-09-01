export default function PageHeader({ title, subtitle, children }) {
  return (
    <header className="page-header">
      <div className="page-header__row">
        <div className="page-header__text">
          <h1>{title}</h1>
          {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
        </div>
        {children && <div className="page-header__actions">{children}</div>}
      </div>
    </header>
  );
}
