---
name: capture
description: Use when the user or another skill explicitely ask for capturing candidate project changes from a conversation or a document. 
---

# Capture changes

Extract, clarify, break down, and file in the inbox all project changes floated or discussed within a conversation or a document. 

This skill acts as a demultiplexer, allowing multiple changes mixed up in a single conversation to become their own independent item that can then be processed in a single thread.

The goal is NOT to have a detailed spec for each change at the end of the process. INSTEAD it is to have a reasonable breakdown of independent items that can be acted on independently afterwards. 

There are a lot of unknowns at this point, so mistakes are expected. Prioritize speed over accuracy.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save items to:** `docs/meanpowers/inbox/YYYY-MM-DD-<item-name>.md`

## Checlikst

You MUST create a task for each of these items and complete them in order:

1. **Read the document or transcript**
2. **Extract project changes**
3. **Update the checklist** in order to insert a documentation task `document <change name>`for each identified change right after the current item. And proceed to document each of the identified change.
4. **Present changes to the user** and iterate on their feedback in order to converge to a validate change items list
5. **Write all validated change items as separate files to the `inbox`**

## The process

**Read and understand the input**

- Read the input: the input might be the current conversation, a previous conversation thread or a document, as instructed by the user.
- Gather the missing context (files, docs, recent commits)

**Extract project changes:**
- Translate the intent into independent project changes
- Categorize them into either:
  - Behaviour change: the intended change should result into a change in how system behaves.
  - Refactoring: the intended change should not change how the system behaves, only its internals.

**Document each change:**
For each change:
- Establish the baseline: document the current system: 
  - What its behaviour is, if it's a behavioural change being documented.
  - How it works internally if it's a refactoring change being documented.
- Establish the target: reframe, from the baseline and the intended change, what the target system would be.

**Review the changes:**
- Run an adversarial review of the changes:
  - Challenge their boundaries
  - Try to aggressively break them up further
- Based on your review insights, come up with 3 different break-downs of the changes
- Choose the best one
- If you identify questions or assumptions that may significantly impact the break-down, ask them one at a time. 

**Present the changes:**
- Present all the changes at once using the following template:
```
CHANGE {i}
Baseline: {1-2 short sentences}
Target: {1-2 short sentences}
Intent: {1 sentence}
-------
```
- Ask "If you have feedback, let's iterate. If not, just say 'ok' and I will write the items to the inbox"
- Act on the feedback if any. Ask clarifying questions as you need. 
- Present the changes to the user.

<HARD-GATE>
Do NOT write any item to the inbox until all changes have been presented and validated by the user. Every revision of the change list must be presented. 
</HARD-GATE>

**Write the changes:**
- For each validated change, create a file to `docs/meanpowers/inbox/YYYY-MM-DD-<item-name>.md`
- Each file should start with the summary that was presented to the user
- Each file should then contain all the context, hypotheses, decisions, regarding that change and that change only.

**Recap what was done:**
- Provide feedback on the list of items that were created. 

