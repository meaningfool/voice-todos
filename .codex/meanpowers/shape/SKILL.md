---
name: shape
description: Use when the user invokes it 
---

# Shape 

## Overview

The `shape` skill is inspired by  Ryan Singer's methodology with my own tweaks. It posits that the understanding of a problem co-evolves with the exploration of solutions. 

In the context of Meanpowers, the `shape` skill provides a process to better define large and/or loosely scoped changes.

## Core concepts

**System:** 
- A software product is a `system` that interacts / is interacted with by the outer world. 
- It is constituted of `components`: components that communicate only with other components are part of the system "internals". Components that are exposed to the outside world are part of the system "interface". 
- The system takes input through its `inbound ports` and reacts through its `outbound ports`.
- The system `behaviour` is described from the `actor`'s perspective by the set of all possible sequences of (input, output), i.e. the `journeys`.

**Actors:**
- `Actors` interact with the system to achieve specific outcomes.
-  Their interactions with the system can be mapped to `journeys` of providing input and receiving output.
- Current journeys are the reflect of the current system. 

**Requirements:**
- The `system designer` knows the actors and its own constraints and objectives. 
- As a result they can infer a state of the system that would better serve the actors and themselves. 
- Their `requirements` are requirements with respect to the system and its components, and with respect to what the actors' journeys should be.
- `requirements` can be defined positively: something that the system does not currently matches but is expected to.
- `requirements` can be defined negatively: something that the sytem currently matches but is not expected to. 

**Shaping:**
- Requirements are points on a map, and `shapes` are versions of the system (and the resulting journeys) that partially or completly link those points.
- `shaping` is the process of converging towards the set of requirements and a matching solution (the `shape`) that best serve the interest represented by the system designer.
- Requirements evolve through the process: they get refined, removed or added. 
- Contrasting multiple options with regards to the system or one of its components highlights new tradeoffs / requirements.

**Slicing:**
- The `shape` is a set of changes to the system 

- The `shape` skill takes a "change" as input, previously formatted as a triplet (`baseline`, `target`, `intent`) by the `capture` skill.