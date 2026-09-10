# Library

> Experimental workspace for the **Library hypothesis** in Hyper-Selenia.
>
> This repository is intentionally isolated. Research, prototypes, notes, tests, and commits produced for this line of work belong here and nowhere else.

## 0. Research boundary

This repository studies one question:

> **Can an evolving system improve itself by repeatedly observing structured traces of its own past perception, action, internal state, and consequences—without reducing those traces to a single scalar memory or a fixed external training signal?**

The working name **Library** comes from a spatial intuition: a system should be able to revisit multiple slices of its own history as inspectable objects, rather than merely carry a compressed residue of the past forward.

The cinematic image of Cooper observing different moments through the bookshelf in *Interstellar* is an analogy, not a mechanism. The earlier “Droste effect” description points to the same intuition: **the observer can inspect a representation in which the observer and the observed system recursively appear across slices**.

Hyper-Selenia gives this intuition a concrete purpose. If the system is expected to evolve itself, then it must have some way to discover:

- what it did,
- what it believed it was doing,
- what actually changed,
- which limitations persisted,
- which changes improved the system,
- and whether the current observer is meaningfully continuous with the historical actor being inspected.

The Library is proposed as the substrate for that process.

---

## 1. Core distinction: memory is not yet a Library

A sequence of stored states is only a history.

A database of events is only an archive.

A weighted summary of the past is only a compressed influence.

For this project, a structure deserves the name **Library** only if the current system can actively revisit historical slices and perform new judgments over them.

A minimal slice may be written as

\[
L_t = (O_t, A_t, I_t, E_t, C_t)
\]

where:

- \(O_t\): what was observed,
- \(A_t\): what action or intervention was applied,
- \(I_t\): inspectable internal state relevant to that decision,
- \(E_t\): resulting external/system change,
- \(C_t\): contextual relations needed to interpret the slice.

This tuple is deliberately provisional. The project should earn its representation experimentally rather than inherit one by convention.

The important property is not the tuple itself. It is **re-observability**:

\[
\text{current system} \rightarrow L_t \rightarrow \text{new judgment at } t' > t
\]

The judgment made at \(t'\) is allowed to disagree with the judgment originally made at \(t\).

That disagreement is not noise. It is one of the primary signals we want to study.

---

## 2. The first original hypothesis: Re-observation Gap

We define a provisional quantity called the **Re-observation Gap**.

Suppose the historical system at time \(t\) made an internal judgment \(J_t\) about a situation. At a later time \(t'\), the current system revisits the same slice and produces \(J_{t' \leftarrow t}\).

Then:

\[
G(t', t) = D(J_t, J_{t' \leftarrow t})
\]

where \(D\) is not assumed to be a conventional embedding distance. It may eventually be structural, behavioral, causal, or task-specific.

The hypothesis is:

> **Persistent, structured re-observation gaps can reveal deficiencies that are invisible to a system that only optimizes current reward or carries forward compressed memory.**

A large gap alone does not mean improvement. The current observer may be worse than the historical one. Therefore the gap must be evaluated against consequences.

This immediately creates a three-way relation:

\[
\text{historical judgment} \leftrightarrow \text{current re-judgment} \leftrightarrow \text{observed consequence}
\]

The Library exists to keep all three inspectable.

---

## 3. The second hypothesis: self-evolution requires an inspectable deficit

A system cannot deliberately repair an unknown deficiency merely because its global score is low.

For self-evolution, we propose a stronger intermediate object:

\[
\Delta_k = \text{a locally inspectable mismatch between expected capability and evidenced capability}
\]

We will call this a **Deficit Object**.

A Deficit Object is not simply an error label. It should contain enough evidence for the system to later ask:

1. What did I expect myself to be able to do?
2. What evidence contradicted that expectation?
3. Was the failure caused by perception, action, coordination, memory, inference, or an invalid self-model?
4. Has a later modification actually removed the deficiency?
5. Did the repair introduce another deficiency elsewhere?

The working evolutionary loop becomes:

\[
\text{act} \rightarrow \text{leave slice} \rightarrow \text{re-observe} \rightarrow \text{construct deficit} \rightarrow \text{modify} \rightarrow \text{re-test against Library}
\]

This is intentionally different from:

\[
\text{act} \rightarrow \text{reward} \rightarrow \text{update}
\]

The project will test whether that difference is real and useful rather than assume it.

---

## 4. Worker / Queen interpretation

Hyper-Selenia contains a Worker/Queen distinction.

The Library must preserve that distinction.

A Worker slice is evidence of **what the Worker experienced**. It must not automatically become a first-person Queen memory.

The Queen may inspect Worker slices, Queen slices, and relations between them. Her task is not merely to aggregate experience, but to form and revise judgments about:

- the capabilities of individual Workers,
- interactions among Workers,
- her own interventions,
- system-level consequences,
- and the relation between historical actors and the present system.

This creates an important constraint:

> **Access does not imply identity.**

If the Queen can read a Worker's history, that does not mean the Queen experienced it.

This distinction will matter when we later study continuity of self, attribution of causality, and responsibility for system changes.

---

## 5. The Library is spatial in organization, not necessarily in storage

Earlier discussion used “slices”, “small cubes”, and the Droste effect. These are useful intuitions, but the implementation does not need literal 3D storage.

The spatial requirement is conceptual:

- slices remain individually addressable,
- relations between slices can be traversed,
- multiple historical viewpoints can coexist without being collapsed immediately,
- the current observer can move between local and system-level views,
- and a slice may itself contain pointers to observations of earlier slices.

This last property creates controlled recursion:

\[
L_{t_3} \rightarrow \text{observation of } L_{t_2} \rightarrow \text{observation of } L_{t_1}
\]

The recursion is valuable only if it changes what can be tested. Infinite self-reference by itself is not intelligence.

---

## 6. What would count as progress?

The project will not treat elegant self-description as success.

A meaningful milestone requires a system to demonstrate at least the following sequence:

1. **Leave evidence** of its own behavior in inspectable slices.
2. **Revisit** selected slices later without receiving the original judgment as an unquestionable truth.
3. **Detect a deficiency** from relations across slices.
4. **Propose a modification** targeted at that deficiency.
5. **Apply the modification** inside a bounded experimental environment.
6. **Re-test historical and novel cases.**
7. **Reject or retain the modification** using evidence generated by the Library.

The strongest version would additionally show that the system can discover a deficiency that was **not explicitly named by the experiment designer**.

---

## 7. Initial milestones

### M0 — Formal vocabulary

Define minimal, falsifiable meanings for:

- Slice
- Observer
- Actor
- Re-observation
- Re-observation Gap
- Deficit Object
- Modification
- Continuity
- Attribution
- Library traversal

Deliverable: a short specification with examples and counterexamples.

### M1 — Toy Library

Build a tiny deterministic world in which an agent acts, leaves slices, and can later inspect them.

No LLM is required.

Goal: prove that the Library mechanics are separable from language-model behavior.

### M2 — Blind deficiency discovery

Construct failures that are visible only when multiple slices are compared.

The current agent must identify the failing relation without being directly told the failure category.

### M3 — Bounded self-modification

Permit a small set of mutable mechanisms or genomes.

A detected Deficit Object may trigger a proposed modification. The modified system must be evaluated against historical slices and held-out situations.

### M4 — Queen / Worker attribution

Introduce multiple Workers and a Queen.

Test whether the Queen can distinguish:

- Worker-local failure,
- communication failure,
- Queen intervention failure,
- and system-level failure.

### M5 — Continuity under change

After several accepted modifications, test whether the current Queen can make useful judgments about the relation between:

- an old Worker,
- an old Queen state,
- the current Queen,
- and the current system.

The objective is not philosophical declaration. It is operational continuity: whether attribution across change improves future decisions.

---

## 8. Anti-goals

At this stage we explicitly avoid:

- assuming that a Transformer or LLM is required,
- equating larger memory with better self-understanding,
- importing a complete existing cognitive architecture and renaming its modules,
- treating vector similarity as self-recognition by default,
- treating recursive self-reference as sufficient evidence of self-awareness,
- optimizing a single scalar and calling the result self-evolution,
- giving the Queen omniscient ground-truth labels during experiments.

Existing theories may later be used as comparison baselines. They should not determine the architecture before the Library earns its own shape experimentally.

---

## 9. Immediate research questions

The next work should answer these experimentally rather than rhetorically:

1. What is the smallest slice that still permits useful re-observation?
2. Which information must remain raw, and which may be compressed?
3. How does the current system choose **which** past slice to inspect?
4. Can a useful deficit emerge from disagreement among several slices rather than one explicit error?
5. How can the system distinguish “I changed” from “the environment changed”?
6. How can Queen attribute an outcome when several Workers contributed?
7. What prevents repeated self-observation from becoming an endless recursive loop?
8. What should be immutable so that self-modification remains testable?
9. Can a modification be locally beneficial but globally destructive, and can the Library expose that fact?
10. At what point does a historical slice cease to be evidence about the current system?

---

## 10. Working thesis

The initial thesis of this repository is:

> **Self-evolution requires more than memory and more than reward. It requires a revisitable structure in which a changing system can observe evidence of what earlier versions perceived, did, expected, and caused; detect structured deficits from disagreement across those slices; and test modifications against both its history and new experience.**

The Library is the experimental name for that structure.

This thesis is provisional. The repository exists to try to break it.
