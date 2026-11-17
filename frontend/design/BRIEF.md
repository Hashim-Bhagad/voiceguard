# VoiceGuard: redesign brief

Renamed from "TRUST & VISHWAS" to "VoiceGuard" at the owner's request during the build.

Partly interviewed, partly authored. The owner's words are quoted; everything else is
marked **Authored**: the owner delegated taste ("use all the frontend design skills you
can", "take a lot of care in the UX") and made two explicit choices (HeroUI-led stack,
Signal Amber palette).

## The eight topics

1. **Vibe.** "I hate the color pallete I need something in black." "A really cinematic
   dark entrance animation." "Some glass effects." **Authored references:** a studio VU
   meter in a dark control room; an oscilloscope trace; the Nothing phone's dot-matrix
   glyphs; the opening title card of a heist film.
2. **Journey, in the owner's words.** An entrance animation; then a hero where "the
   mouse hover has the effect of the pixeled voice bars going up and down"; then things
   that reveal "as people are scrolling", with "a dribble effect". **Authored order:**
   below.
3. **Energy curve (authored).** Loud open (entrance and hero), quiet tension, the peak
   at the live demo, calm and precise for the model explainer, warm for proof, a firm
   close.
4. **Feeling and the one moment (authored).** See the feeling curve and the peak below.
5. **The thing no other site does (authored).** The hero's voice bars react to the
   cursor and expose the clone: the left half moves like a human voice, the right half
   like a synthetic one. Crossing the midline makes the bars snap rigid and a readout
   flips to SYNTHETIC. The site demonstrates the detector before you read a word.
6. **Distance from premium-minimal (authored).** Precision instrument rather than
   minimal: dark, technical, dense where the data is real, generous everywhere else.
7. **One world or distinct scenes (authored).** Distinct scenes. Each section behaves
   differently; no continuous camera flight.
8. **Assets.** The owner's logo (`public/logo.png`) and the real model results. The
   owner will generate photography from the prompts in the handover; every section
   works without it.

## Who it is for

Recruiters and engineers opening a portfolio project, plus anyone checking a suspicious
call. **What they must believe by the end:** this detector is real, it works on cloned
voices in Indian languages, and you can try it right now. **The one action:** "Try a
sample call", used everywhere.

## Journey

| Beat | Section | What changes for the visitor |
|---|---|---|
| Recognition | Hero | A voice they can see, and the clone half that gives itself away |
| Tension | The call | A familiar voice asking for money is now a solved problem for attackers |
| Turn (peak) | Live demo | They pick a call, watch it get scored, and see the verdict |
| Substance | Inside the model | How 4 seconds of audio becomes one number |
| Proof | Results | Real numbers from the held-out test and real clones |
| Verify | Liveness | When the score is unsure, ask for proof |
| Commitment | Close | Try your own audio, or read the model |

## Feeling curve

| Act | Feeling | Cause on screen |
|---|---|---|
| Entrance | Anticipation | One flat line on black spikes into a heartbeat and becomes the bars |
| Hero | Curiosity, then a small shiver | Bars follow the cursor; past the midline they turn rigid and read SYNTHETIC |
| The call | Unease | A slow, quiet line-by-line reveal of a familiar scam |
| Live demo | Control, relief | You run a real sample; the score climbs, the verdict lands |
| Inside the model | Respect | A pinned diagram builds, layer by layer, as you scroll |
| Results | Trust | Real numbers count up next to the test that produced them |
| Liveness | Reassurance | A fresh challenge irises open; the digits appear |
| Close | Resolve | The bars return, calm, and the single action waits |

**Peak:** the live demo. "You pick a scam call and watch the site catch the cloned voice
in front of you." It gets the most scroll room and the most motion; the section before
it is the quietest.

**Tell-someone sentence:** "It's the site where the voice bars change when your cursor
crosses into the clone, and then it catches a fake call while you watch."

**Authored silence:** "The call" is deliberately sparse, with no motion except the text
itself.

## Rules adopted from the skills

- No scroll cue, no `01 / 06` counters, at most one eyebrow per three sections, no em
  dashes in visible copy, no gradient text, no neon halo glows.
- Real numbers only: 2.97% EER, 0.996 ROC-AUC, 16 of 16 team clones caught, 5
  languages, 6,646 training clips, 101M of 316M parameters trained.
- Glass on two layers only: the navigation and the verdict card.
- Animate transform, opacity, clip-path and filter only. Reduced motion gets fades and
  a static frame of the bars.
- One filled amber action per view.
