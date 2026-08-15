import { HiOutlineMagnifyingGlass } from "react-icons/hi2";

export default function SearchField({
  value,
  onChange,
  placeholder = "Buscar…",
  disabled = false,
  className = "",
}) {
  return (
    <div className={`relative ${className}`}>
      <HiOutlineMagnifyingGlass
        className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-mocha/50"
        aria-hidden
      />
      <input
        type="text"
        className="input w-full pl-10 pr-3 transition-shadow focus:ring-2 focus:ring-caramel/30"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
    </div>
  );
}
