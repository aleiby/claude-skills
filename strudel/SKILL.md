---
name: strudel
description: Use when composing music in Strudel.cc, writing Strudel pattern code, extracting beat events, or rendering audio. Covers the REPL, Node.js validation, pattern language, sounds, effects, and export pipeline.
---

# Strudel.cc — Live Coding Music

## Overview

Strudel is an open-source browser-based live coding environment for music, ported from TidalCycles to JavaScript. No account, login, or API token needed. No MCP server.

- **Web REPL**: https://strudel.cc — paste code, press Ctrl+Enter. No install.
- **Node.js**: `@strudel/core` + `@strudel/mini` + `@strudel/tonal` for headless pattern validation and event extraction. No audio playback (requires browser Web Audio API).
- **License**: AGPL-3.0 (source code). Compositions/audio output are yours.

## Development Workflow

1. **Author** `.js` composition files
2. **Validate** on Linux via Node.js — parse patterns, extract events, check timing/density
3. **Listen** in Chrome on Mac — user pastes code into strudel.cc REPL
4. **Iterate** based on user feedback

### Node.js Setup

The project has `@strudel/core`, `@strudel/mini`, and `@strudel/tonal` installed. A postinstall script patches a broken `@kabelsalat/web` dependency in `@strudel/core/repl.mjs` (not needed for headless use).

```bash
npm install   # installs deps + runs postinstall patch
```

### Validation Tool

`tools/strudel-validate.mjs` provides headless pattern evaluation:

```bash
# Validate a composition file (looks for exported patterns)
node tools/strudel-validate.mjs <composition.js>

# Or import in scripts
import { note, s, n, stack, queryPattern, printPattern } from './tools/strudel-validate.mjs';

printPattern(note('c3 e3 g3 c4'), 1, 'My pattern');
// Output: beat positions, durations, values, event count

const events = queryPattern(myPattern, 4);  // structured event data
```

Composition files should export patterns as named exports:
```js
export const drums = s("bd sd hh sd");
export const bass = note("c2 ~ e2 ~").s("sawtooth");
```

### What Validation Can Check

- Pattern syntax (does it parse?)
- Event timing and count
- Note density per cycle
- Lane distribution
- Correct Euclidean/polymetric output
- Scale degree resolution

### What Validation Cannot Check

- How it sounds (requires browser)
- Whether sample/sound names exist
- Effect parameter results
- Audio mix quality

## Core Concepts

### Cycles

The fundamental time unit. 1 cycle = 1 bar.

```js
setcps(0.5)           // cycles per second (0.5 = 120 BPM in 4/4)
setcpm(30)            // cycles per minute

// BPM conversion: setcps(bpm / 60 / beats_per_bar)
setcps(120 / 60 / 4)  // 120 BPM, 4/4
setcps(156 / 60 / 7)  // 156 BPM, 7/8
```

### Mini-Notation

```js
"a b c d"          // 4 events per cycle, equally spaced
"a b [c d]"        // c and d subdivide into the space of one
"a ~ b ~"          // ~ = rest
"a*4"              // repeat 4 times in its slot
"a!4"              // replicate (stretch, not speed up)
"a(3,8)"           // Euclidean rhythm: 3 hits across 8 slots
"a(3,8,2)"         // Euclidean with rotation offset
"<a b c>"          // alternate each cycle
"a@3 b@1"          // a gets 3/4 of the cycle, b gets 1/4
"[a b]@2 [c d e]@3"  // asymmetric groupings (useful for odd meters)
"a,b"              // a and b play simultaneously (polyphony)
"{a b c, d e}"     // polymetric: left over right's structure
```

### Pattern Functions

```js
note("c3 e3 g3")              // pitch by note name
n("0 2 4 6").scale("C:minor") // scale degrees
freq(440)                      // frequency in Hz
s("bd sd hh sd")              // sample/synth name
```

### Layering

```js
stack(pattern1, pattern2, pattern3)  // play simultaneously
$: pattern1                          // REPL: each $: is a parallel voice
$: pattern2
```

### Arrangement

```js
arrange(
  [1, stinger],   // 1 cycle
  [4, intro],     // 4 cycles
  [8, bodyA],     // 8 cycles
  [8, bodyB],
)
// Loops when done

melody.mask("<0!8 1!8>")  // silent 8 cycles, audible 8
s("bd ~ sd bd").every(4, x => x.fast(2))     // double-time every 4th
s("bd ~ sd bd").lastOf(8, x => x.rev())      // reverse every 8th
s("bd sd hh sd").sometimesBy(0.3, ply(2))    // random stutter 30%
```

### Time Modifiers

```js
pattern.fast(2)       // double speed
pattern.slow(4)       // quarter speed
pattern.rev()         // reverse
pattern.iter(n)       // rotate start position each cycle (Clapping Music)
pattern.off(0.25, x => x.add(note(7)))  // canon: delayed copy a 5th up
```

## Sound Sources

All sounds work out of the box in the strudel.cc REPL — no downloads or setup needed. Built-in synths are generated locally via Web Audio API oscillators. Sample-based sounds (GM SoundFont, VCSL, drum machines) are lazy-loaded from CDN on first trigger. Expect a brief silence on the very first hit of a new sample while it downloads; subsequent plays are instant.

| Type | Source | Loaded From |
|------|--------|-------------|
| Synths (`sine`, `square`, `supersaw`) | Generated in browser | Web Audio API oscillators |
| GM SoundFont (`gm_trombone`, etc.) | WebAudioFont data | CDN (GeneralUser/FluidR3 SF2) |
| VCSL (`sax`, `timpani`) | CC0 samples | `strudel.b-cdn.net` |
| Drum machines (`.bank("RolandTR909")`) | tidal-drum-machines | CDN |
| Custom (`samples(...)`) | User-specified | GitHub repos, URLs, or local server |

### Built-in Synths

```js
note("c4").s("sine")       // pure tone
note("c4").s("square")     // chiptune
note("c4").s("sawtooth")   // buzzy lead
note("c4").s("triangle")   // soft bass
note("c4").s("pulse")      // variable duty cycle
note("c4").s("supersaw")   // detuned unison
  .unison(7).detune(0.3).spread(0.8)
```

### FM Synthesis

```js
note("c4").s("sine")
  .fm(4)           // modulation index (brightness)
  .fmh(2)          // harmonicity ratio (timbre)
  .fmattack(0.01).fmdecay(0.3).fmsustain(0.2)

// Metallic bell: .fm(8).fmh(3.5)
// Bass: .fm(2).fmh(1).fmdecay(0.5)
// Inharmonic/metallic: non-integer fmh (1.61, 2.3, 3.7)
```

### GM SoundFont Samples

Orchestral instruments prefixed with `gm_`:

| Category | Examples |
|----------|----------|
| Brass | `gm_trumpet`, `gm_trombone`, `gm_tuba`, `gm_french_horn`, `gm_muted_trumpet`, `gm_brass_section` |
| Strings | `gm_string_ensemble_1`, `gm_tremolo_strings`, `gm_cello`, `gm_contrabass` |
| Pads/FX | `gm_pad_metallic`, `gm_fx_atmosphere`, `gm_fx_goblins`, `gm_choir_aahs` |
| Melodic Perc | `gm_vibraphone`, `gm_marimba`, `gm_xylophone`, `gm_celesta`, `gm_tubular_bells` |

Usage: `note("c4 e4 g4").s("gm_trombone")`

### VCSL Samples (CC0)

`sax`, `sax_stacc`, `sax_vib`, `saxello`, `timpani`, `timpani_roll`, `pipeorgan_loud`, `harmonica`

### Drum Machines

```js
s("bd sd hh sd").bank("RolandTR909")
```

72 machines available: `RolandTR808`, `RolandTR909`, `RolandTR606`, `LinnDrum`, `EmuSP12`, `OberheimDMX`, `SimmonsSDS5`, etc.

### Noise

`white`, `pink`, `brown`, `crackle`

### Custom Samples

```js
samples('github:user/repo')                        // from GitHub
samples({ name: ['file.wav'] }, 'https://url/')    // direct URL
// Local: npx @strudel/sampler -> samples('http://localhost:5432/')
```

Samples lazy-load on first trigger (see Sound Sources table above).

## Effects Reference

| Category | Effect | Parameters |
|----------|--------|------------|
| Filter | `.lpf(hz)`, `.hpf(hz)`, `.bpf(hz)` | 0-20000 Hz |
| Resonance | `.lpq(n)`, `.bpq(n)` | 0-50 |
| Filter type | `.ftype(n)` | 0=12dB, 1=ladder (aggressive), 2=24dB |
| Filter env | `.lpenv(depth)`, `.lpa()`, `.lpd()`, `.lps()`, `.lpr()` | |
| Distortion | `.distort(n)` | 0-10+ |
| Saturation | `.shape(n)` | 0-1 |
| Bitcrush | `.crush(n)` | 1-16 (lower = harsher) |
| Sample rate | `.coarse(n)` | 1-32 |
| ADSR | `.attack(t).decay(t).sustain(l).release(t)` | seconds / 0-1 |
| Pitch env | `.penv(semitones)`, `.pdec(t)` | |
| Vibrato | `.vib(speed)`, `.vibmod(depth)` | |
| Reverb | `.room(n)`, `.rsize(n)` | send 0-1, size 0-10 |
| Delay | `.delay(n)`, `.delaytime(t)`, `.delayfeedback(n)` | |
| Pan | `.pan(n)` | 0=L, 0.5=C, 1=R |
| Stereo | `.jux(fn)` | right-channel transform |
| Phaser | `.phaser(speed)`, `.phaserdepth(n)` | |
| Compressor | `.compressor("thresh:ratio:knee:att:rel")` | |
| Volume | `.gain(n)` | 0-1+ |
| FX bus | `.orbit(n)` | shared effects routing |
| Global | `all(x => x.room(0.2).lpf(9000))` | apply to all patterns |

**Processing order:** coarse -> crush -> shape -> distort -> tremolo -> compressor -> pan -> phaser -> postgain -> orbit (delay + reverb)

## Scales and Harmony

```js
n("0 2 4 6").scale("C:minor")
n("0 2 4 6").scale("<C:phrygian Eb:harmonic:minor>")  // key change per cycle
```

Available scales include: `major`, `minor`, `dorian`, `phrygian`, `lydian`, `mixolydian`, `locrian`, `harmonic:minor`, `phrygian:dominant`, `hungarian:minor`, `double:harmonic:major`, `whole:tone`, `pentatonic`, `blues`

## Polyrhythms and Euclidean Rhythms

```js
s("bd(3,8)")                    // 3 hits across 8 slots
s("bd(3,8,2)")                  // with rotation offset
stack(
  s("bd(3,7)"),                 // 3 against 7
  s("rim(2,7,3)"),              // 2 against 7, offset 3
  s("hh(5,7)")                  // 5 against 7
)
```

## Event Extraction (queryArc)

Query a pattern for its events over a time range:

```js
const haps = pattern.onsetsOnly().queryArc(startCycle, endCycle);

haps.forEach(hap => {
  const beat = hap.whole.begin.valueOf();  // start time in cycles
  const end = hap.whole.end.valueOf();     // end time in cycles
  const onset = hap.hasOnset();            // true if note-on
  const value = hap.value;                 // { note, s, ... }
});
```

**Key rule:** Query individual patterns BEFORE `stack()`-ing to get clean per-track data.

## Audio Rendering / Export

Strudel has **no native audio/MIDI file export**. Options:

1. **Playwright + MediaRecorder** (automatable): Solo each pattern in browser, record via Web Audio API MediaRecorder. Output webm/opus -> convert to OGG/WAV with ffmpeg.
2. **MIDI to DAW** (highest quality): `.midichan(n).midi('IAC Driver')`. Record in DAW. Render stems.
3. **OBS / browser capture** (simplest): Solo manually, record with OBS.

All stems must use the same `cps` and run for the same number of cycles. Duration = `totalCycles / cps` seconds.

## MIDI Output

```js
note("c3 e3 g3").midi()                    // default MIDI output
note("c3 e3 g3").midichan(1).midi('IAC Driver')  // specific channel + device
```

Requires WebMIDI (browser only). Supports clock/transport messaging.

## Metadata Tags

```js
// @title My Composition
// @by Author Name
// @license CC0
// @details bpm=120 timeSig=4/4
```

## Licensing

- **Strudel source**: AGPL-3.0 — embedding the runtime in a shipped app triggers AGPL. Using it as an offline tool to produce assets does not.
- **VCSL samples**: CC0 (safe to ship)
- **ZZFX synth**: MIT (safe)
- **AKWF wavetables**: verify before shipping
- **Custom samples**: track provenance — not all Freesound/community samples are CC0
