# Spoken self-corrections

Available in **Falco 2.6.2**. This release improves explicit “no” and “not that”
cue handling, including corrections across pauses, and accepts verified short
corrections that the normal length check previously rejected.

Enable **Settings → Refiner → Refine dictation** and finish any model download.
Speak the replacement before releasing the dictation key:

- **“Meet me on Monday, no, Tuesday.”** → **“Meet me on Tuesday.”**
- **“Use red paint, not that, blue paint.”** → **“Use blue paint.”**
- **“Order two boxes of screws, no wait, three boxes.”** → **“Order three boxes of screws.”**
- **“Email the draft to Alice and copy Ben, I mean Carol.”** →
  **“Email the draft to Alice and copy Carol.”**

You can also use **I mean**, **make that**, **scratch that** and **or rather**.
These are corrections to what you are dictating, rather than instructions for
Command Mode. A bare “no” is ambiguous; “no wait” plus the replacement is clearer.
Ordinary statements such as **“I have no problem with that”** and
**“It is not that important”** should keep their negation.

## Pauses and final text

In normal dictation, the refiner receives the transcript before the completed
text is typed. It is instructed to remove abandoned wording and the correction
phrase, keep the replacement, and preserve unrelated details. DFlash is optional
and does not need to be enabled for this behavior.

With **Type at pause**, an earlier phrase may already be on screen. If the next
phrase clearly corrects it, Falco can replace that phrase within the same
recording. It checks the edit's structure and the typing destination before
backspacing; if the edit cannot be verified or typing is no longer safe, it
keeps the earlier text and types the new phrase as spoken. It does not reach
back through arbitrary earlier recordings or edit a different application.

The normal length check remains in place. An unusually short result is allowed
only for short transcripts (up to 64 words), when the existing structural
correction check can account for the removed words. Longer transcripts retain
the normal length guard. A correction cue alone does not authorize arbitrary deletion of details.
Model interpretation is still fallible; a vague “not that” without a replacement
is not a reliable command to delete a specific earlier passage.

## Validation

The change has 26 regression cases covering explicit cues, ordinary negations,
sentence boundaries, unsafe edits, the short-result guard, prefetch and the
Type at pause replacement path. The pinned Phonon Q4_K_S target was also checked
with 15 synthetic transcripts, including corrections, literal negations,
reported speech, questions and instruction-like text. These are functional
checks, not an accuracy or speed benchmark. Microphone transcription and
compositor-level text insertion were not exercised by that model check.
