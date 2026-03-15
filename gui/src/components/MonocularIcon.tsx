interface MonocularIconProps {
  width?: number;
  height?: number;
  className?: string;
}

export function MonocularIcon({ width = 22, height = 14, className }: MonocularIconProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 22 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={className}
    >
      {/* Eyepiece */}
      <rect x="0" y="4" width="3" height="6" rx="1" fill="#f5a623" opacity="0.75"/>
      {/* Main barrel */}
      <rect x="2" y="2" width="10" height="10" rx="1.5" fill="#f5a623" opacity="0.9"/>
      {/* Objective housing (wider flare) */}
      <rect x="10.5" y="0" width="4" height="14" rx="1.5" fill="#f5a623" opacity="0.7"/>
      {/* Objective lens ring */}
      <circle cx="18" cy="7" r="3.8" stroke="#f5a623" strokeWidth="1.4" fill="rgba(245,166,35,0.1)"/>
      {/* Lens glass fill */}
      <circle cx="18" cy="7" r="2.2" fill="rgba(245,166,35,0.08)" stroke="#f5a623" strokeWidth="0.5" opacity="0.6"/>
      {/* Lens shine */}
      <circle cx="16.6" cy="5.4" r="0.9" fill="#f5a623" className="logo-lens-shine"/>
    </svg>
  );
}
