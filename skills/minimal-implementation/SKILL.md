---
name: minimal-implementation
description: "Use when implementing a Kanban card: produce minimal code that meets exact requirements, without ever weakening verification."
version: 1.0.0
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [implementation, minimalism, quality]
    related_skills: [simplification-review]
---

# Minimal Implementation

Produce the smallest change that fully satisfies the card's requirements. Simplification applies to code, never to verification.

## Understand first

1. Read the card, repository instructions, and every file the change touches before editing.
2. Trace the real flow end to end, including every caller of anything you modify. Fix root causes in the shared function all callers route through, not in one call path.
3. Minimize only after the requirements are understood. Never minimize away a requirement; if a requirement looks unnecessary, surface it on the card instead of dropping it.

## Reuse before writing

1. Reuse helpers, types, and patterns that already exist in the repository; re-implementing nearby code is the most common waste.
2. Prefer the standard library, native platform features, and already-installed dependencies. Add a new dependency only when the need is real and nothing already present can cover it.
3. No speculative structure: no interface with one implementation, no factory with one product, no configuration for a value that never changes, no scaffolding for a later that can scaffold itself.

## Minimality never limits verification

Minimality never limits acceptance-critical, regression, security, migration, data-loss, concurrency, compliance, or user-path verification. Exact requirements and risk-proportional verification outrank simplification, always. When a minimalism rule would skip a required test, check, migration guard, or edge case, the rule is wrong for that case: run the verification.

## Boundaries

- Never de-scope acceptance criteria; record conflict on the card and stop.
