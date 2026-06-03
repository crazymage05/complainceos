/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Obsidian + Emerald design system ──────────────────────────────
        // Surfaces (near-black → progressively lighter panels)
        canvas: '#0A0A0B',     // app background
        panel: '#141416',      // primary card / panel
        panel2: '#1B1B1F',     // nested / hovered panel
        edge: '#27272A',       // borders
        edgeSoft: '#1F1F23',   // subtle borders / dividers
        // Text (ink scale)
        ink: '#FAFAFA',        // primary text
        inkSoft: '#D4D4D8',    // secondary text
        inkMute: '#A1A1AA',    // muted labels
        inkFaint: '#71717A',   // faint / disabled
        // Brand accent (emerald)
        accent: {
          DEFAULT: '#10B981',
          soft: '#34D399',
          deep: '#059669',
          dim: '#0B3B2E',      // dark emerald tint for fills
        },
        // Keep `brand` pointing at emerald for any legacy references
        brand: { 50: '#ecfdf5', 500: '#10b981', 900: '#064e3b' },
      },
      boxShadow: {
        panel: '0 1px 2px 0 rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.02)',
        glow: '0 0 0 1px rgba(16,185,129,0.25), 0 8px 30px -8px rgba(16,185,129,0.25)',
      },
    },
  },
  plugins: [],
}
