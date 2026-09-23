/* =====================================================
   ICONS

   Inline SVG, currentColor, 1.7 stroke throughout so
   they read as one set. Every icon is decorative -
   the control around it carries the accessible name.
===================================================== */

type IconProps = {
  size?: number;
};

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

export function PdfIcon({ size = 18 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M8 13h2" />
      <path d="M8 17h8" />
      <path d="M13 13h3" />
    </svg>
  );
}

export function PlusIcon({ size = 18 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export function SendIcon({ size = 17 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M22 2L11 13" />
      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
    </svg>
  );
}

export function MicIcon({ size = 18 }: IconProps) {
  return (
    <svg {...base(size)}>
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10v2a7 7 0 0 0 14 0v-2" />
      <path d="M12 19v3" />
      <path d="M8 22h8" />
    </svg>
  );
}

export function CopyIcon({ size = 14 }: IconProps) {
  return (
    <svg {...base(size)}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export function CheckIcon({ size = 14 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

export function CloseIcon({ size = 15 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </svg>
  );
}

export function LayersIcon({ size = 18 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 2L2 7l10 5l10-5l-10-5Z" />
      <path d="M2 17l10 5l10-5" />
      <path d="M2 12l10 5l10-5" />
    </svg>
  );
}

export function NewChatIcon({ size = 17 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1l1-4Z" />
    </svg>
  );
}

export function SparkIcon({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 3v4" />
      <path d="M12 17v4" />
      <path d="M3 12h4" />
      <path d="M17 12h4" />
      <circle cx="12" cy="12" r="3.2" />
    </svg>
  );
}

export function SummaryIcon({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 5h16" />
      <path d="M4 10h16" />
      <path d="M4 15h10" />
      <path d="M4 20h7" />
    </svg>
  );
}

export function FindingsIcon({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.2-3.2" />
    </svg>
  );
}

export function FinanceIcon({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 19V9" />
      <path d="M10 19V5" />
      <path d="M16 19v-7" />
      <path d="M22 19H2" />
    </svg>
  );
}

export function RiskIcon({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M10.3 3.9L1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function PanelIcon({ size = 17 }: IconProps) {
  return (
    <svg {...base(size)}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M15 3v18" />
    </svg>
  );
}

export function MenuIcon({ size = 18 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M3 6h18" />
      <path d="M3 12h18" />
      <path d="M3 18h18" />
    </svg>
  );
}
