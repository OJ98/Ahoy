---
name: academic-writing
description: 'Edit and review academic papers following Dr. Munindar P. Singh writing guidelines. Use when: writing or editing LaTeX papers, reviewing academic prose for grammar and style, checking BibTeX references, formatting figures and tables, proofreading drafts, writing research papers. Triggers: academic writing, paper editing, LaTeX, BibTeX, grammar review, proofreading, Dr. Singh style.'
argument-hint: 'Paste text or specify file to review'
---

# Academic Writing — Dr. Singh's Guidelines

Apply these rules when editing or reviewing academic papers. For the full comprehensive reference, see [guidelines.md](./references/guidelines.md).

## When to Use
- Editing or reviewing LaTeX academic papers
- Proofreading drafts before submission
- Checking grammar, style, and formatting
- Reviewing BibTeX references
- Formatting figures, tables, and captions

## Review Procedure

When asked to edit or review academic text, follow these steps:

### Step 1: Structural Check
- Every section has 0 or ≥2 subsections
- Every list has ≥2 items
- Figures referenced from main text
- Table captions at top, figure captions at bottom (sentence case, end with period)
- Page numbers present; title, author, date on title page

### Step 2: Grammar & Style Pass
Apply these high-priority rules (see [full reference](./references/guidelines.md) for complete list):

**Sentence Structure:**
- Given-then-new order: known information first, new information after
- Active voice (almost always)
- "We" not "I" for authors; vary with "This paper develops..." / "Section 3 shows..."
- Delete text that adds no meaning — if removing it costs nothing, remove it
- Don't switch perspective across sentences (e.g., "fetching" then "returning")

**Word Choice — Forbidden:**
- No slashes (scientists/researchers), no and/or, no etc.
- No content-free words: actually, basically, really, essentially, very, relatively, kind of, sort of, at this point in time
- No "feel" ("we feel that") — use "believe" or omit
- No "believe" about others — use "claim"
- No "while" for "whereas" (while = concurrent)
- No "have to" — use "must"
- No "firstly/secondly" — use "first/second"
- No "furthermore" — use "further"
- No "lots of" — use "several"
- No "get" — use "obtain"
- No "allow" unless you mean permission — usually "enable" or "facilitate"
- No "utilize" — use "use"
- No contractions in formal writing (don't, we'll, can't)
- "Though" at sentence start → "although"
- "Different from" NOT "different than"
- "Less than" NOT "lesser than"

**Technical Word Traps:**
- "Implies/entails" — technical terms in CS; use carefully
- "Deduce" — most inferences are not deductions; prefer "infer"
- "System" — always specify which system
- "Consistency" — in CS means logical consistency, not uniformity
- "Alternate" (back and forth) ≠ "alternative" (choice)
- "Monotonous" (boring) ≠ "monotonic" (math property)

**Determiners & Articles:**
- "Figure 3" ✓ or "the figure" ✓ — NOT "the Figure 3" ✗
- Use "it/its" for impersonal objects (agents, tables); "he/she" for people
- "Each" and "every" take singulars
- Mass nouns never plural: advice, code, evidence, information, research, software

**Punctuation:**
- "e.g.," and "i.e.," always with commas; never begin a sentence with them
- Oxford comma: "A, B, and C" ✓
- "That" (restrictive) vs "which" (non-restrictive, needs commas)
- "However" starts a new sentence, never joins clauses with comma
- Hyphens for compound modifiers ("run-time error" but "at run time")
- Don't hyphenate when prefix isn't standalone ("redo" not "re-do")
- En-dashes for ranges (--), em-dashes for parentheticals (---)

**Citations:**
- Use author names: "Chopra [3] says..." — never "The authors of [3]..."
- Don't begin sentence with citation, bracket, numeral, or lowercase letter
- Space before citation: "text [3]" not "text[3]"
- Always specify comparisons: "faster than X" not just "faster"

### Step 3: LaTeX-Specific Check
- Quotes: `` `correct' `` not "wrong"
- Ties before refs: `Section~\ref{sec-foo}`
- `\texttt{}` or `\textsf{}` for code, never math fonts for multi-letter identifiers
- `$A_1$` for identifiers with numerals; `\mathrm{FP}` in subscripts
- `\url{}` for URLs and URL-like text
- Avoid "the following figures" / "the above figures" — LaTeX moves floats
- No hard constants for internal references; always use `\ref`
- Don't include standard styles (ACM, IEEE) in Overleaf projects

### Step 4: BibTeX Check
- Full first names: "George B. Shaw" not "G.B. Shaw"
- Braces for string fields, bare numbers for numeric fields
- Title case for booktitle/journal; BibTeX lowercases article titles automatically
- Protect capitalized words: `{Internet}`, `{Web}`, `{BERT}`
- After colon in title, capitalize next word: `{Life on the {Internet}: A Brief Report}`
- Remove redundant info from DBLP proceedings titles
- Supply DOI if available; else URL; else ISBN
- Supply page numbers, articleno, numpages
- Month field: three-letter symbols (jan, feb) not strings
- Author format: `{First1 M1. Last1 and First2 M2. Last2}`

### Step 5: Prepositions Audit
Check for these common errors:
- Ancestor **of** (not to), centered/focused **on** (not around)
- "Comprises" or "consists of" — never "comprises of"
- "Discuss" (not "discuss about"), "emphasize" (not "emphasize on")
- "Consider" (not "consider about"), "comply with" (not "comply to")
- "Called" / "considered" — never "called as" / "considered as"
- Avoid redundant togetherness: "combining together", "cooperating together"

### Step 6: Final Checklist
- [ ] "Related Work" not "Related Works"
- [ ] No etc., slashes, and/or in formal text
- [ ] Figure captions at bottom (sentence case); table captions at top
- [ ] Numbers ≤10 as words; ≥1,000 with commas; years without commas
- [ ] No past/future tense for paper structure ("Section 5 presents...")
- [ ] Active voice throughout
- [ ] That vs which used correctly
- [ ] Citations include author names and have preceding space
- [ ] All sections have 0 or ≥2 subsections; all lists have ≥2 items
- [ ] Spell check complete; then proofread
- [ ] No footnotes (decide if it belongs in main text or not)
- [ ] New terms introduced with italics, not quotes
- [ ] Emphasis (bold/italics) used sparingly
- [ ] Consistent list formatting (all capitalized or all lowercase; all with periods or none)
