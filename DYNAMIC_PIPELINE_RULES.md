# Dynamic Pipeline Isolation Rules

## Purpose

This document is the guardrail for all work on the new Dynamic workflow.

## Non-Negotiable Rule

**DO NOT modify, refactor, rename, replace, delete, or repurpose the existing/old pipeline in order to build the Dynamic pipeline.**

The existing pipeline is already working and must remain available with its current behavior.

## Old Pipeline

The old pipeline must remain independent and untouched.

- Existing Workflow remains the old workflow.
- Existing Outline logic remains unchanged.
- Existing Opus Writer Prompt remains unchanged.
- Existing Writer files and outputs remain unchanged.
- Existing agents, prompts, gates, production behavior, and naming must not be changed merely to support the Dynamic workflow.
- Do not migrate old behavior into Dynamic by editing the old implementation.

If a future Dynamic feature appears to require changing an old-pipeline file, stop and treat that as an architecture conflict rather than silently modifying the old pipeline.

## Dynamic Pipeline

All new experimental structure work belongs to the separate Dynamic workflow.

Planned separation:

1. Dynamic Outline
2. Dynamic Writer Prompt
3. Dynamic Final Script

Dynamic components should use their own files, logic, UI, and outputs wherever practical so they do not override or interfere with old-pipeline behavior.

## Dynamic Output Naming

New Dynamic-generated Markdown artifacts should use a clear `Dynamic_` prefix so they cannot be confused with old-pipeline artifacts.

Examples:

- `Dynamic_05_script_outline.md`
- `Dynamic_05_writer_prompt.md`
- `Dynamic_06_final_script.md`

Exact Dynamic filenames may evolve as the Dynamic workflow is designed, but they must remain clearly separate from old outputs.

## Dynamic Outline Strategy

The Dynamic Outline Builder is a separate experimental control plane. Its JSON strategy can contain user-defined parent blocks, child blocks, ordering, instructions, enabled/disabled state, and optional repeat/interval placement settings.

The Dynamic architecture should allow new structures to be created without hardcoding specific creative block names into the old pipeline.

## Current Scope

At the time this guardrail was created, the Dynamic Outline Builder saves its strategy JSON separately. Future integration with a Dynamic Outline Agent or Dynamic Writer must be implemented on the Dynamic path, not by converting the existing old workflow into the Dynamic workflow.

## Rule for Future Development

Before making a Dynamic workflow change, ask:

> Can this be implemented in the Dynamic path without changing the old pipeline?

If yes, implement it only in the Dynamic path.

If no, do not modify the old pipeline automatically. The architecture must be reviewed first and explicit approval obtained before touching old-pipeline behavior.

**Old pipeline = preserve. Dynamic pipeline = develop separately.**
