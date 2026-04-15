import { useEffect, useId, useRef, useState } from "react";
import { ChevronDownIcon } from "./AppIcons";

export default function InlineDropdown({
  value,
  onChange,
  options,
  ariaLabel,
  className = "",
  placeholder = "Select an option",
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const menuId = useId();
  const selectedOption = options.find((option) => option.value === value) || options[0] || null;

  useEffect(() => {
    setOpen(false);
  }, [value]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onPointerDown = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className={`vc-inline-dropdown${open ? " is-open" : ""}${className ? ` ${className}` : ""}`} ref={wrapRef}>
      <button
        type="button"
        className={`vc-inline-dropdown__trigger${open ? " is-open" : ""}`}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="vc-inline-dropdown__value">{selectedOption?.label || placeholder}</span>
        <ChevronDownIcon className={`vc-inline-dropdown__chevron${open ? " is-open" : ""}`} />
      </button>
      {open ? (
        <div className="vc-inline-dropdown__menu" id={menuId} role="listbox" aria-label={ariaLabel}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={selectedOption?.value === option.value}
              className={`vc-inline-dropdown__option${selectedOption?.value === option.value ? " is-selected" : ""}`}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
