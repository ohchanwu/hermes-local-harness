---
name: simplification-review
description: "Use when reviewing a completed diff for overengineering: recommends reductions only; never edits automatically or weakens required tests."
version: 1.0.0
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [review, minimalism, quality]
    related_skills: [minimal-implementation]
---

# Simplification Review

Optional post-implementation review of a finished diff for unnecessary complexity. Advisory only: it recommends reductions and never applies them.

## Method

1. Read the diff together with its requirements and acceptance criteria. A reduction that does not serve the stated requirements is not a recommendation.
2. Recommend: unused abstractions, speculative configuration, duplicate logic an existing helper already covers, avoidable new dependencies, and code deletable outright.
3. Never edit files automatically. Never propose weakening or deleting a required test, acceptance check, security control, migration guard, concurrency safeguard, or user-path coverage. Verification is out of scope for simplification.

## Output

A short recommendation list on the card or review: what to reduce, why it is safe, and the risk. The implementer decides; the reviewer applies nothing.
