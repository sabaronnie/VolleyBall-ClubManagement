import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDownIcon } from "./AppIcons";

export default function InlineDropdown({
  value,
  onChange,
  options,
  ariaLabel,
  className = "",
  placeholder = "Select an option",
  disabled = false,
  valueLabel = "",
  portal = false,
}) {
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState(null);
  const wrapRef = useRef(null);
  const menuRef = useRef(null);
  const menuId = useId();
  const selectedOption = options.find((option) => option.value === value) || null;
  const displayLabel = selectedOption?.label || valueLabel || placeholder;

  useEffect(() => {
    setOpen(false);
  }, [value]);

  useLayoutEffect(() => {
    if (!open || !portal || !wrapRef.current) {
      setMenuStyle(null);
      return undefined;
    }

    const updateMenuPosition = () => {
      const rect = wrapRef.current.getBoundingClientRect();
      setMenuStyle({
        position: "fixed",
        top: `${rect.bottom + 7}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`,
        maxHeight: `${Math.max(180, window.innerHeight - rect.bottom - 20)}px`,
      });
    };

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, portal]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onPointerDown = (event) => {
      const inTrigger = wrapRef.current?.contains(event.target);
      const inMenu = menuRef.current?.contains(event.target);
      if (!inTrigger && !inMenu) {
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

  const selectOption = (option) => {
    onChange(option.value);
    setOpen(false);
  };

  const menu = open && !disabled ? (
    <div
      className={`vc-inline-dropdown__menu${portal ? " vc-inline-dropdown__menu--portal" : ""}`}
      id={menuId}
      role="listbox"
      aria-label={ariaLabel}
      ref={menuRef}
      style={portal && menuStyle ? menuStyle : undefined}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="option"
          aria-selected={selectedOption?.value === option.value}
          className={`vc-inline-dropdown__option${selectedOption?.value === option.value ? " is-selected" : ""}`}
          onPointerDown={(event) => {
            event.preventDefault();
            selectOption(option);
          }}
          onClick={(event) => {
            if (event.detail === 0) {
              selectOption(option);
            }
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  ) : null;

  return (
    <div className={`vc-inline-dropdown${open ? " is-open" : ""}${className ? ` ${className}` : ""}`} ref={wrapRef}>
      <button
        type="button"
        className={`vc-inline-dropdown__trigger${open ? " is-open" : ""}`}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        disabled={disabled}
        onClick={() => {
          if (!disabled) {
            setOpen((current) => !current);
          }
        }}
      >
        <span className="vc-inline-dropdown__value">{displayLabel}</span>
        <ChevronDownIcon className={`vc-inline-dropdown__chevron${open ? " is-open" : ""}`} />
      </button>
      {portal && menu ? createPortal(menu, document.body) : menu}
    </div>
  );
}
