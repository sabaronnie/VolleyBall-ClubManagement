export function BellIcon({ className = "app-icon", title = null }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <path d="M12 2.75a5.75 5.75 0 0 0-5.75 5.75v2.32c0 .86-.24 1.7-.69 2.43L4.5 14.98A1.75 1.75 0 0 0 5.98 17.7h3.56a2.5 2.5 0 0 0 4.92 0h3.56a1.75 1.75 0 0 0 1.48-2.72l-1.06-1.73a4.65 4.65 0 0 1-.69-2.43V8.5A5.75 5.75 0 0 0 12 2.75Zm1.18 14.95a1.25 1.25 0 0 1-2.36 0h2.36Z" />
    </svg>
  );
}

export function UserCircleIcon({ className = "app-icon", title = null }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <path d="M12 2.75a9.25 9.25 0 1 0 0 18.5 9.25 9.25 0 0 0 0-18.5Zm0 3.6a3.15 3.15 0 1 1 0 6.3 3.15 3.15 0 0 1 0-6.3Zm0 12.15a7.97 7.97 0 0 1-5.36-2.06 5.9 5.9 0 0 1 10.72 0A7.97 7.97 0 0 1 12 18.5Z" />
    </svg>
  );
}

export function ChevronDownIcon({ className = "app-icon", title = null }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
