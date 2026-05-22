import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: [
  				'var(--font-inter)',
  				'system-ui',
  				'sans-serif'
  			]
  		},
  		colors: {
  			accent: {
  				DEFAULT: 'var(--accent)',
  				hover: 'var(--accent-hover)',
  				deep: 'var(--accent-deep)',
  				subtle: 'var(--accent-subtle)'
  			},
  			success: {
  				DEFAULT: 'var(--status-success)',
  				bg: 'var(--status-success-bg)',
  				border: 'var(--status-success-border)'
  			},
  			warning: {
  				DEFAULT: 'var(--status-warning)',
  				bg: 'var(--status-warning-bg)',
  				border: 'var(--status-warning-border)'
  			},
  			danger: {
  				DEFAULT: 'var(--status-danger)',
  				bg: 'var(--status-danger-bg)',
  				border: 'var(--status-danger-border)'
  			},
  			info: {
  				DEFAULT: 'var(--status-info)',
  				bg: 'var(--status-info-bg)',
  				border: 'var(--status-info-border)'
  			},
  			ai: {
  				DEFAULT: 'var(--ai-generated)',
  				bg: 'var(--ai-generated-bg)'
  			},
  			brain: {
  				DEFAULT: 'var(--app-brain)',
  				bg: 'var(--app-brain-bg)'
  			},
  			canvas: 'var(--bg-base)',
  			surface: 'var(--bg-surface)',
  			elevated: 'var(--bg-elevated)',
  			line: {
  				DEFAULT: 'var(--border-default)',
  				subtle: 'var(--border-subtle)',
  				strong: 'var(--border-strong)'
  			},
  			ink: {
  				DEFAULT: 'var(--text-primary)',
  				secondary: 'var(--text-secondary)',
  				tertiary: 'var(--text-tertiary)'
  			},
  			background: 'var(--bg-base)',
  			foreground: 'var(--text-primary)',
  			card: {
  				DEFAULT: 'var(--bg-surface)',
  				foreground: 'var(--text-primary)'
  			},
  			popover: {
  				DEFAULT: 'var(--bg-surface)',
  				foreground: 'var(--text-primary)'
  			},
  			primary: {
  				DEFAULT: 'var(--primary)',
  				foreground: '#ffffff'
  			},
  			secondary: {
  				DEFAULT: 'var(--bg-elevated)',
  				foreground: 'var(--text-primary)'
  			},
  			muted: {
  				DEFAULT: 'var(--bg-elevated)',
  				foreground: 'var(--text-tertiary)'
  			},
  			destructive: {
  				DEFAULT: 'var(--status-danger)',
  				foreground: '#ffffff'
  			},
  			border: 'var(--border-default)',
  			input: 'var(--border-default)',
  			ring: 'var(--accent)'
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		boxShadow: {
  			card: 'var(--shadow-card)',
  			soft: 'var(--shadow-md)',
  			lift: 'var(--shadow-lg)'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: { height: '0' },
  				to: { height: 'var(--radix-accordion-content-height)' }
  			},
  			'accordion-up': {
  				from: { height: 'var(--radix-accordion-content-height)' },
  				to: { height: '0' }
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
