interface MonocularIconProps {
  width?: number;
  height?: number;
  className?: string;
}

export function MonocularIcon({ width = 22, height = 14, className }: MonocularIconProps) {
  // viewBox is 38x24 — monocular body (left) + tiny compass (right)
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 38 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={className}
    >
      {/* ── Monocular ── */}

      {/* Eyecup */}
      <rect x="0" y="7" width="2.5" height="10" rx="0.8"
        fill="#1a1206" stroke="#f5a623" strokeWidth="0.5"/>

      {/* Main barrel */}
      <rect x="2" y="5" width="11" height="14" rx="1.2"
        fill="#1a1206" stroke="#f5a623" strokeWidth="0.6"/>

      {/* Grip rings on barrel */}
      <line x1="5.5" y1="5" x2="5.5" y2="19" stroke="#3a2a05" strokeWidth="0.4"/>
      <line x1="7"   y1="5" x2="7"   y2="19" stroke="#3a2a05" strokeWidth="0.4"/>

      {/* Focus wheel */}
      <rect x="9" y="3.5" width="2.2" height="17" rx="0.8"
        fill="#1a1206" stroke="#f5a623" strokeWidth="0.5"/>

      {/* Objective housing (tapered) */}
      <path d="M13,5 L13,19 L16,21 L16,3 Z"
        fill="#1a1206" stroke="#f5a623" strokeWidth="0.5"/>

      {/* Objective lens ring */}
      <circle cx="21" cy="12" r="5.5"
        fill="#0d1520" stroke="#f5a623" strokeWidth="0.9"/>
      {/* Lens glass */}
      <circle cx="21" cy="12" r="4"
        fill="#061830" stroke="#f5a623" strokeWidth="0.4" opacity="0.9"/>
      {/* Lens reflection arc */}
      <path d="M18.5,9 A4,4 0 0,1 23.5,9"
        stroke="#f5a623" strokeWidth="0.5" fill="none" opacity="0.5"/>
      {/* Lens center dot */}
      <circle cx="21" cy="12" r="0.8" fill="#f5a623" opacity="0.9"/>
      {/* Lens crosshair */}
      <line x1="18.5" y1="12" x2="23.5" y2="12"
        stroke="#f5a623" strokeWidth="0.4" opacity="0.35"/>
      <line x1="21" y1="9" x2="21" y2="15"
        stroke="#f5a623" strokeWidth="0.4" opacity="0.35"/>
      {/* Shine spot */}
      <circle cx="19.6" cy="10.4" r="0.7" fill="#f5a623" opacity="0.4"/>

      {/* ── Tiny Compass (bottom-right corner) ── */}
      {/* Outer ring */}
      <circle cx="33.5" cy="18.5" r="4"
        fill="#0d1018" stroke="#f5a623" strokeWidth="0.6"/>
      {/* Cardinal ticks */}
      <line x1="33.5" y1="14.5" x2="33.5" y2="15.3" stroke="#f5a623" strokeWidth="0.5"/>
      <line x1="33.5" y1="21.7" x2="33.5" y2="22.5" stroke="#f5a623" strokeWidth="0.5"/>
      <line x1="29.5" y1="18.5" x2="30.3" y2="18.5" stroke="#f5a623" strokeWidth="0.5"/>
      <line x1="36.7" y1="18.5" x2="37.5" y2="18.5" stroke="#f5a623" strokeWidth="0.5"/>
      {/* Inner face */}
      <circle cx="33.5" cy="18.5" r="2.2"
        fill="#0d1520" stroke="#f5a623" strokeWidth="0.4"/>
      {/* Needle N (amber) */}
      <polygon points="33.5,16.4 33.0,18.7 33.5,19.1 34.0,18.7"
        fill="#f5a623"/>
      {/* Needle S (dark) */}
      <polygon points="33.5,20.6 33.0,18.3 33.5,17.9 34.0,18.3"
        fill="#3a3020" stroke="#f5a623" strokeWidth="0.3"/>
      {/* Center pivot */}
      <circle cx="33.5" cy="18.5" r="0.7" fill="#f5a623"/>
      <circle cx="33.5" cy="18.5" r="0.35" fill="#0a0b0d"/>
    </svg>
  );
}
