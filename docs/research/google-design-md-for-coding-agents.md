---
title: Google DESIGN.md for Coding Agents
created: 2026-05-01
updated: 2026-05-01
type: research-note
tags: [google, design-md, coding-agents, system-prompt]
sources:
  - https://github.com/google-labs-code/design.md
  - https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
confidence: high
---

# Google DESIGN.md for Coding Agents

## Verified wording

Google Labs Code's `design.md` README says:

> A format specification for describing a visual identity to coding agents. DESIGN.md gives agents a persistent, structured understanding of a design system.

The spec says:

> DESIGN.md is a self-contained, plain-text representation of a design system. It defines the visual identity of a brand and product, thereby ensuring that these stylistic choices can be followed across design sessions and between different AI agents and tools. As a human-readable, open-format document, it serves as a living source of truth that both humans and AI can understand and refine.

## Practical interpretation for Hermes

Use DESIGN.md as a first-class prompt context file for visual identity and design rationale, separate from coding/process instructions in AGENTS.md or CLAUDE.md. This lets multiple agents/tools share the same design system without copying long prompts into every task.
