# Design debt register

Living document. First audit: 2026-11-17 (frontend, after the VoiceGuard redesign).
Priority = severity (Critical 3, Moderate 2, Minor 1) × frequency ÷ effort (Low 1, Med 2, High 3).
Review quarterly, and before any redesign.

## Resolved on 2026-11-17

| ID | Category | Sev | Issue | Fix |
|---|---|---|---|---|
| A1 | A11y | Critical | Smooth-scroll handler swallowed every in-page link, so the skip link and nav anchors moved the page but not keyboard focus | `useLenis` focuses the target after scrolling; every `<main>` has `tabIndex={-1}` |
| A4 | A11y | Critical | Footer disclaimer set in `--grey-700` (3.1:1, marked "never text") | `text-muted` |
| I1 | Impl | Minor | 36 unreachable source files and 3 unused public assets from the old design (old brand included) | Deleted (all were tracked in git) |
| I2 | Impl | Mod | Seven copies of token-to-colour helpers with 23 hex fallbacks, one already out of sync | `src/lib/tokens.js` (`token`, `toRgb`, `rgbToken`), no fallbacks |
| I3 | Impl | Minor | Dead `.hairline`, two unused easing tokens, unused `Section`, unused `colors.dim` | Removed |
| I4 | Impl | Minor | `firebase`, `geist`, `gsap` unused (gsap only drove Lenis's ticker) | Uninstalled; Lenis runs `autoRaf` |
| V1 | Visual | Minor | Raw `[var(--x)]` colour utilities | `grey-700`, `paper`, `hairline` exposed in `@theme`; components use `bg-hairline`, `bg-grey-700`, `decoration-amber-hot`, `fill-muted` |
| V2 | Visual | Mod | Red used for non-danger: record-stop buttons, retry button, "code expired", offline dot | Primary/secondary buttons, warning for expiry, grey for offline. Phone hang-up buttons in the landing mockup keep red on purpose (universal phone vocabulary) |
| V8 | Visual | Mod | Backend status drawn two ways (landing vs workspace) | Same colours and wording in both |
| C1 | Copy | Mod | Six names for verification | Action: "Verify the caller". Noun: "liveness check" |
| C2 | Copy | Mod | Same voice score under six labels | "Voice spoof score" in Verify and History; "Voice model" stays only as the contribution row name |
| C3 | Copy | Mod | Landing promises Bengali, language hint lacked it | Bengali added to the hint list |
| C4 | Copy | Mod | Three threshold sets (.7/.4, .55/.35, .5) | `STANDARD` in `lib/analysis.js` mirrors the backend; `verdict()` uses it. The .5 challenge trigger matches the backend's own rule |
| C5 | Copy | Minor | Em dash as the empty value | "n/a" |
| A2 | A11y | Minor | `animate-pulse` and programmatic smooth scroll ignored reduced motion | Global reduce rule; scroll uses `auto` under reduced motion |
| A3 | A11y | Mod | Ticking seconds counter and whole result panels inside live regions | One `role="status"` line per state (current step; "Analysis complete…") |
| A5 | A11y | Minor | `aria-label` on elements with no role | `role="img"`/`role="group"`, or visually hidden text (ScrubWords) |
| A6 | A11y | Mod | Hero readout re-announced on every auto-sweep | Live only after the visitor moves the pointer |
| A7 | A11y | Minor | Step lists didn't expose state | `aria-current="step"` plus hidden "done / in progress" text |
| S1 | Struct | Mod | Workspace links were raw anchors (full reload, lost analysis); landing mobile menu had no Escape | `<Link>`; Escape closes and returns focus |
| S4 | Struct | Minor | 404 page used an ad-hoc button and sans heading | Shared `Cta`, display type, grain |

## Open

| ID | Category | Sev | Effort | Issue | Plan |
|---|---|---|---|---|---|
| V3 | Visual | Mod | Med | Tone maps duplicated (`app/tones.js`, `DemoSection`, `Verify`) with different icons; two pipeline step lists with different copy | One `lib/tones.js` (label, icon, colour var) and one `STEPS` list |
| V4 | Visual | Mod | Med | Workspace headings are sans semibold, landing uses `font-display`; workspace h2 in four sizes; display h2 class string pasted five times | Heading components or type tokens (h1/h2/h3) shared by both surfaces |
| V5 | Visual | Mod | Med | `.glass` on six layers (rule says two); two card recipes (`bg-ink-1 rounded-3xl` vs `bg-surface rounded-2xl`) | Name two or three surface recipes with fixed radii; decide which layers keep glass |
| V6 | Visual | Minor | Low | Hand-built mono labels instead of `.label-mono` (Analyze line header, demo panel header, Result tags) | Use `.label-mono`, add a size modifier if needed |
| V7 | Visual | Mod | Med | Four button systems (`Cta`, HeroUI `buttonVariants`, ad-hoc buttons, size overrides with `!`) | Build `Cta` on `buttonVariants`; add a link-button variant |
| S2 | Struct | Mod | High | Verify and History don't share the redesigned language (no line instrument, own verdict layouts) | Reuse `VerdictCard`, `explain()` and the Line on both |
| S3 | Struct | Minor | Med | URL slugs don't match labels (`/challenge`, `/log`); legacy `/dashboard/alert` redirect | Rename to `/verify`, `/history`; keep redirects from old paths |
| C6 | Copy | Minor | Med | Storage keys use the old `tv-` prefix | Rename to `vg-` with a one-time migration |
| A8 | A11y | Mod | Low | Verify page result section is one large live region | Same pattern as Analyze: a single status line |

## Not verified

Contrast was taken from the token comments, not measured on rendered pixels. Screen-reader output for HeroUI Table, Tabs and Select is untested. Keyboard focus fixes were verified in headless Chromium (skip link, nav anchors), not with a screen reader.
