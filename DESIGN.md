---
version: alpha
name: Hermes Agent Design Context
description: Compact design-system source of truth for Hermes Agent, Agent Board, generated reports, dashboards, and design skills.
colors:
  primary: "#111827"
  secondary: "#4B5563"
  tertiary: "#7C3AED"
  neutral: "#F8FAFC"
  surface: "#FFFFFF"
  success: "#10B981"
  warning: "#F59E0B"
  danger: "#EF4444"
typography:
  h1:
    fontFamily: Inter
    fontSize: 2.25rem
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.03em"
  body-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.6
  mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: 500
    lineHeight: 1.5
rounded:
  sm: 6px
  md: 12px
  lg: 20px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: 12px
  report-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.lg}"
    padding: 24px
  report-muted-card:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.md}"
    padding: 16px
  status-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 8px
  status-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 8px
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: 8px
---

# Hermes Agent Design Context

## Overview

DESIGN.md is the design source of truth for Hermes Agent work. Google describes DESIGN.md as "a format specification for describing a visual identity to coding agents" that gives agents "a persistent, structured understanding of a design system"; its spec calls it a living source of truth that humans and AI can understand and refine. Treat this file as the compact, inline-indexed layer for design decisions in system prompts.

Use this file when creating or reviewing: Agent Board UI, browser artifacts, dashboards, decks, Discord/CEO reports, generated HTML tools, design skills, and visual QA. Use `AGENTS.md` / `CLAUDE.md` for coding/process instructions; use this file for look, feel, interaction, artifact surfaces, and design-system references.

## Colors

Hermes should feel calm, operational, and trustworthy: dark ink text, pale neutral backgrounds, one violet agent accent, and semantic status colors. Use accent color sparingly for primary action, active agent state, and selected artifact. Avoid rainbow dashboards unless the user explicitly requests exploratory visualization.

## Typography

Use Inter or a system sans fallback for UI/report text. Use JetBrains Mono or a system monospace fallback for commands, paths, IDs, logs, and model/provider names. Prioritize scanability: short headings, dense but readable cards, and tables only when comparison matters.

## Layout

Default surfaces are artifact-first: left/right split, file or run tree near the artifact, preview in the main pane, tool/todo stream nearby, and concise next action at the bottom. Discord reports should be compact: decision, evidence, action, risk. Browser artifacts should work as single-file HTML where possible.

## Elevation & Depth

Use shallow elevation only to separate cards, active panels, modals, and preview frames. Prefer borders, spacing, and hierarchy over heavy shadows.

## Shapes

Use moderate rounding (`md`/`lg`) for cards and controls. Keep tables, logs, and code blocks crisp. Device/browser frames may be used for mobile or product mockups, but do not redraw them when a reusable frame asset exists.

## Components

- **Agent Board:** artifact tree, iframe/markdown preview, run graph, tool stream, todo stream, comment-to-refine anchors.
- **Ops dashboard:** status cards, risk/severity chips, last verified time, evidence links, next safe action.
- **Report artifact:** TL;DR, decision needed, evidence URLs, changes made, verification, next checkpoint.
- **Design skill output:** declare output surface, preview entry, required design-system sections, quality gate, and capabilities.

## Do's and Don'ts

Do:
- Read this file before design-related generation or review.
- Prefer one active design system per artifact; if borrowing from references, state the chosen reference.
- Keep generated artifacts previewable and self-contained unless a framework is required.
- Add semantic anchors such as `data-hermes-id` / `data-od-id` to major artifact regions for targeted refinement.
- Verify accessibility basics: contrast, focus, keyboard path, reduced motion.

Don't:
- Copy Open Design assets/code blindly; reinterpret patterns in Hermes-native skills and UI.
- Mix many brand systems in one artifact.
- Let decorative polish hide operational facts, timestamps, risks, or evidence.
- Treat screenshots as source of truth when editable DESIGN.md/tokens/components exist.

## Reference Index

Primary external specs and research:
- Google DESIGN.md repo: https://github.com/google-labs-code/design.md
- Google DESIGN.md spec: https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
- Nexu Open Design clone: `/home/mqz/.hermes/research/open-design/nexu-open-design`
- Local wiki: `/home/mqz/.hermes/research/open-design/wiki`
- Hermes integration note: `/home/mqz/.hermes/research/open-design/wiki/concepts/hermes-integration-opportunities.md`
- Open Design skill catalog: `/home/mqz/.hermes/research/open-design/wiki/concepts/open-design-skill-catalog.md`

Open Design DESIGN.md library, all files at `/home/mqz/.hermes/research/open-design/nexu-open-design/design-systems/<name>/DESIGN.md`:
`airbnb`, `airtable`, `apple`, `binance`, `bmw`, `bugatti`, `cal`, `claude`, `clay`, `clickhouse`, `cohere`, `coinbase`, `composio`, `cursor`, `default`, `elevenlabs`, `expo`, `ferrari`, `figma`, `framer`, `hashicorp`, `ibm`, `intercom`, `kraken`, `lamborghini`, `linear-app`, `lovable`, `mastercard`, `meta`, `minimax`, `mintlify`, `miro`, `mistral-ai`, `mongodb`, `nike`, `notion`, `nvidia`, `ollama`, `opencode-ai`, `pinterest`, `playstation`, `posthog`, `raycast`, `renault`, `replicate`, `resend`, `revolut`, `runwayml`, `sanity`, `sentry`, `shopify`, `spacex`, `spotify`, `starbucks`, `stripe`, `supabase`, `superhuman`, `tesla`, `theverge`, `together-ai`, `uber`, `vercel`, `vodafone`, `voltagent`, `warm-editorial`, `warp`, `webflow`, `wired`, `wise`, `x-ai`, `xiaohongshu`, `zapier`

Open Design skill reference set, all files at `/home/mqz/.hermes/research/open-design/nexu-open-design/skills/<name>/SKILL.md`:
`audio-jingle`, `blog-post`, `critique`, `dashboard`, `dating-web`, `digital-eguide`, `docs-page`, `email-marketing`, `eng-runbook`, `finance-report`, `gamified-app`, `guizang-ppt`, `hr-onboarding`, `hyperframes`, `image-poster`, `invoice`, `kanban-board`, `magazine-poster`, `meeting-notes`, `mobile-app`, `mobile-onboarding`, `motion-frames`, `pm-spec`, `pricing-page`, `replit-deck`, `saas-landing`, `simple-deck`, `social-carousel`, `sprite-animation`, `team-okrs`, `tweaks`, `video-shortform`, `web-prototype`, `weekly-update`, `wireframe-sketch`

## Hermes Integration Priorities

1. Make `DESIGN.md` load alongside `AGENTS.md`/`CLAUDE.md` so design context survives coding sessions.
2. Update creative skills to declare output surface, preview entry, design-system dependency, and quality gate.
3. Strengthen Agent Board around artifact preview, file tree, run graph, and comment-to-refine loops.
4. Port only the smallest durable ideas from Open Design first: `dashboard`, `web-prototype`, `critique`, `tweaks`, `weekly-update`, `eng-runbook`.
