/** Design tokens from stitch "Modern Quantitative Precision" DESIGN.md */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F7F8FA",
        ink: { DEFAULT: "#0F172A", 2: "#475569", 3: "#64748B", 4: "#94A3B8" },
        line: { DEFAULT: "#E2E8F0", strong: "#CBD5E1", soft: "#F1F5F9" },
        teal: { DEFAULT: "#0F766E", hover: "#115E59", tint: "#F0FDFA", ring: "#CCFBF1", 400: "#2DD4BF", 300: "#5EEAD4" },
        pos: { DEFAULT: "#16A34A", wash: "#DCFCE7" },
        warn: { DEFAULT: "#D97706", wash: "#FEF3C7" },
        alert: { DEFAULT: "#DC2626", wash: "#FEE2E2", tint: "#FEF2F2" },
        info: { DEFAULT: "#2563EB", wash: "#DBEAFE" },
        lavender: "#EEF2FF",
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
      borderRadius: { md: "0.5rem", lg: "0.75rem", xl: "1rem" },
      boxShadow: {
        card: "0 1px 3px 0 rgba(15,23,42,0.04), 0 1px 2px -1px rgba(15,23,42,0.02)",
        raised: "0 4px 6px -1px rgba(15,23,42,0.06), 0 2px 4px -2px rgba(15,23,42,0.03)",
        modal: "0 20px 25px -5px rgba(15,23,42,0.08), 0 8px 10px -6px rgba(15,23,42,0.04)",
      },
      fontSize: {
        kpi: ["32px", { lineHeight: "38px", letterSpacing: "-0.02em", fontWeight: "600" }],
        "label-sm": ["11px", { lineHeight: "14px", letterSpacing: "0.02em", fontWeight: "500" }],
      },
    },
  },
  plugins: [],
};
