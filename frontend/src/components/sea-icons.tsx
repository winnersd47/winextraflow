/**
 * Sea-themed SVG icons — replace emojis throughout the platform.
 * Each icon is 20x20 by default, uses currentColor.
 */

const s = 20; // default size

// Wave/Flow — signals, main
export const IconWave = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/><path d="M2 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" opacity=".5"/></svg>
);

// Compass — navigation, leaderboard
export const IconCompass = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" fill="currentColor" opacity=".3"/></svg>
);

// Anchor — backtest, stability
export const IconAnchor = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="5" r="3"/><line x1="12" y1="8" x2="12" y2="21"/><path d="M5 12H2a10 10 0 0020 0h-3"/></svg>
);

// Ship — marketplace, trade
export const IconShip = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M2 21c2-1 4-1 6 0s4 1 6 0 4-1 6 0"/><path d="M4 17l1.5-9h13L20 17"/><path d="M12 3v5"/><path d="M8 8h8"/></svg>
);

// Helm — copy trading, steering
export const IconHelm = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/></svg>
);

// Lightning/Bolt — execution, speed
export const IconBolt = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
);

// Telegram/Sail — telegram channels
export const IconSail = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 2L4 20l8-4 8 4L12 2z"/><line x1="12" y1="16" x2="12" y2="22"/></svg>
);

// Net — referrals, connections
export const IconNet = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><line x1="12" y1="7" x2="5" y2="17"/><line x1="12" y1="7" x2="19" y2="17"/><line x1="5" y1="19" x2="19" y2="19"/></svg>
);

// Shield/Verify — KYC
export const IconShield = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
);

// Pearl/Gem — premium
export const IconPearl = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3h12l4 6-10 13L2 9z"/><path d="M2 9h20"/><path d="M12 22L6 9"/><path d="M12 22l6-13"/></svg>
);

// Radar — capacity monitoring
export const IconRadar = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6" opacity=".5"/><circle cx="12" cy="12" r="2"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
);

// Diver — profile
export const IconDiver = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a6 6 0 0112 0v2"/></svg>
);

// Plus/Create — create signal
export const IconPlus = ({ size = s }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
);
