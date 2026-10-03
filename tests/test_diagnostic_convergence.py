#!/usr/bin/env python3
"""Static policy contracts, not a runtime dispatcher or permission grant."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
POLICY = "policies/diagnostic-convergence.md"
ORCHESTRATOR = "skills/multi-agent-coding-orchestrator/SKILL.md"
DEPLOYMENT = "skills/devops/production-deployment/SKILL.md"
AUTHORITY = "policies/authority-and-review.md"


def require(path, *clauses):
    text = (ROOT / path).read_text()
    for clause in clauses:
        assert clause in text, f"{path}: missing contract: {clause}"
    return text


for path in (POLICY, ORCHESTRATOR, DEPLOYMENT):
    require(path,
            "Reject likely-INDETERMINATE probes that do not change the next action",
            "sealed reusable controller requires written justification",
            "first material review correction",
            "second material failure or exhausted",
            "external-read/write, credential, mutation, deployment, and cutover HUMAN GATEs",
            "pre-provider", "no external-call units", "completed provider request")
for path in (POLICY, ORCHESTRATOR):
    require(path,
            "`work_kind: diagnostic`", "`decision_to_unlock`", "`hypothesis`",
            "`minimum_probe`", "`risk_tier`", "`outcome_to_next_action`", "`complexity_budget`",
            "at most two design generations per hypothesis",
            "require a strategy pivot or abandon the probe",
            "campaign-level problem solving, not unlimited refinement of one diagnostic design",
            "trusted direct command → local synthetic repro → one-off bounded script → sealed reusable controller")
require(ORCHESTRATOR,
        "Attach for diagnostic design, including infrastructure diagnostics",
        "Leave off for ordinary implementation",
        "verification and safety outrank minimalism, never the reverse",
        "recorded strategy pivot before another eligible `RETRY_TERMINAL`",
        "Never use terminal retry for user stop/pause/revocation",
        "Provider, quota, crash, timeout, unavailable-model, and context-exhaustion",
        "It never covers pushes, PR creation, deployments, production mutations",
        "Those conditions are `HUMAN_BLOCK`")
require(AUTHORITY,
        "Review proportionality and decision utility before implementation minutiae",
        "direct simplify/pivot/abandon rather than serial micro-fixes",
        "proven local pre-provider failure consumes no external-call units",
        "each completed provider request consumes one",
        "Missing semantics or extensions require owner approval",
        "No push, PR, deploy, credential change, or automatic deletion is authorized here")
require(DEPLOYMENT,
        "A deployment plan or specification is not authorization to perform them",
        "obtain approval for the temporary lock write",
        "Apply private infrastructure only after its bounded approval",
        "Present the cutover packet and obtain explicit approval",
        "cleanup requires separate approval")

# Validate local destinations in the touched docs, including reference definitions.
for path in (POLICY, ORCHESTRATOR, DEPLOYMENT, AUTHORITY, "docs/README.md",
             "docs/archive/261003-diagnostic-convergence.md"):
    text = (ROOT / path).read_text()
    links = re.findall(r"\]\(([^)]+)\)", text)
    links += re.findall(r"^\s*\[[^\]]+\]:\s+(\S+)", text, re.M)
    for link in links:
        if "://" not in link and not link.startswith("#"):
            assert (ROOT / path).parent.joinpath(link.split("#")[0]).exists(), (path, link)

print("ok: diagnostic convergence policy, retained gates, and documentation links")
