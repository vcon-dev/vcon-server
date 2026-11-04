# Motion scene player

This folder holds four animated scenes of the open source server. Each scene has a static Mermaid twin in `docs/diagrams/`.

Open `index.html` in a browser. It runs over `file://` with no build step, no server and no network. A hash picks the scene: `index.html#m3`.

| Tab | Scene | File | Twins |
|---|---|---|---|
| M1 | A vCon runs a chain | `scenes/m1-chain-run.js` | D01, D05 |
| M2 | Workers drain the ingress queues | `scenes/m2-workers.js` | D06 |
| M3 | A vCon gains analysis, tags and attachments | `scenes/m3-vcon-assembly.js` | D07, D10 |
| M4 | A failed vCon reaches the DLQ and returns | `scenes/m4-dlq-recovery.js` | D08, D09 |

## Keep these file rules

- Scene files are classic scripts. Browsers block ES modules, `fetch` and XHR over `file://`, so use none of them.
- Load nothing from a CDN. Fonts sit in `fonts/` and styles in `shell.css`.
- Use vanilla JavaScript and SVG, with no libraries.
- A scene changes only its own file. Add a shared style or helper in `shell.css` or `shell.js`, not in a scene.

## Register a scene

Each scene file makes one call to `VconMotion.register`. A malformed scene throws a `TypeError` at load. Its tab then shows an error and the other tabs keep working.

```js
VconMotion.register({
  id: 'm1',                         // matches the tab in index.html
  title: 'A vCon runs a chain',     // shown above the stage
  summary: 'One sentence on what the viewer sees.',
  twins: ['D01-system-context', 'D05-chain-pipeline'], // file names in docs/diagrams, no extension
  viewBox: [960, 540],              // optional, this is the default

  setup: function (ctx) {
    // Build the SVG once, in the state before step 1. Keep handles in ctx.state.
    var a = ctx.node({ x: 100, y: 238, label: 'Source' });
    var b = ctx.node({ x: 405, y: 238, label: 'Target' });
    ctx.state.path = ctx.edge({ from: a.right, to: b.left });
    ctx.state.token = ctx.token({ x: a.cx, y: a.y - 24 });
  },

  steps: [
    {
      id: 'move',                   // stable name, used by tests
      label: 'The token moves',     // short heading in the step list
      caption: 'One or two plain sentences. Screen readers announce this.',
      duration: 1200,               // ms of animation
      hold: 700,                    // optional ms pause after the step, default 700
      draw: function (p, ctx) {     // p runs from 0 to 1, linear
        ctx.state.token.follow(ctx.state.path, ctx.ease(p));
      }
    }
  ]
});
```

## Follow the drawing contract

The shell rebuilds the stage on every jump: it runs `setup`, then calls `draw(1, ctx)` on each finished step in order. So Back, Step, Reset and the step list all work with no scene code, as long as these rules hold.

- `draw` depends only on `p`, `ctx` and what earlier steps left at `p = 1`. Set values. Never add to them.
- `draw(1, ctx)` alone must produce the full end state of the step. The shell may skip every smaller `p`.
- Do all motion inside `draw`. Use no timers, `requestAnimationFrame`, CSS transitions or SMIL, since the shell could not pause or skip them.
- Put meaning in the captions as well as the picture. Reduced motion viewers and screen readers rely on them.
- Never signal a state by colour alone. The `fail` state uses a dark fill and a dashed line for this reason.
- Every caption must come from the code, like any other page in these docs. Mark what you cannot confirm with `TODO(verify)` in a code comment, not in a caption.

## Build with the stage helpers

`setup` and `draw` receive the same `ctx`. It is rebuilt on each mount, so `ctx.state` starts empty.

| Member | Purpose |
|---|---|
| `ctx.svg`, `ctx.width`, `ctx.height` | Root SVG element and its viewBox size |
| `ctx.layers` | SVG groups from back to front: `back`, `edges`, `nodes`, `tokens`, `notes` |
| `ctx.tokens` | Brand colours: `green`, `greenDeep`, `ink`, `body`, `muted`, `surface`, `white` |
| `ctx.state` | Scratch object for the scene |
| `ctx.reducedMotion` | True when the viewer asks for reduced motion |
| `ctx.el(tag, attrs, parent)` | Creates an SVG element. The parent defaults to `layers.notes` |
| `ctx.text({ x, y, text, kind, anchor, parent })` | Adds text. `\n` splits lines. `kind` is `label`, `title` or `small` |
| `ctx.setText(textEl, value)` | Replaces the text of an element made by `ctx.text` |
| `ctx.node({ x, y, w, h, label, sub, state })` | Adds a box. Defaults to 150 by 64 |
| `ctx.edge({ from, to, via, label, dashed, state })` | Adds an arrow through `[x, y]` points |
| `ctx.token({ x, y, label, w, h, state, hidden })` | Adds a moving card, centred on `x, y`. The label defaults to `vCon` |
| `ctx.show(item, visible)`, `ctx.fade(item, opacity)` | Work on an element or on anything a helper returned |
| `ctx.ease(p)` | Brand easing, `cubic-bezier(.2, .7, .2, 1)` |
| `ctx.lerp(a, b, p)`, `ctx.clamp(v, lo, hi)` | Interpolate and limit. `clamp` defaults to 0 and 1 |
| `ctx.seg(p, a, b)` | Maps the window `a` to `b` of a step onto 0 to 1 |

Helper return values:

- A node has `g`, `x`, `y`, `w`, `h`, `cx`, `cy`, the `[x, y]` ports `left`, `right`, `top` and `bottom`, plus `setLabel(label, sub)` and `setState(state)`.
- An edge has `g`, `points`, `pointAt(p)` and `setState(state)`.
- A token has `g`, `at(x, y)`, `follow(edge, p)`, `setLabel(text)` and `setState(state)`.

States are `idle`, `active`, `done`, `fail` and `muted`. Edges have no `done` style, and tokens show `active` as `idle`. Node labels do not wrap, so size boxes to fit. Keep SVG text at 12px or larger in the 960 wide viewBox. The stage stops shrinking at 640px and scrolls inside its frame on phones.

## Drive the player

`window.VconMotion` carries the whole API.

| Call | Effect |
|---|---|
| `register(scene)` | Adds a scene. Call it from a scene file |
| `select(id)` | Shows a scene at its start and stops playback |
| `play()` | Plays from the current position. At the end it restarts |
| `pause()` | Stops playback and keeps the frame |
| `step()` | Stops playback and finishes the current step |
| `step(-1)` | Stops playback and returns to the start of the step, or of the step before when already on a boundary |
| `seek(cursor, p)` | Jumps to a position, for tests and screenshots. `cursor` counts finished steps |
| `reset()` | Returns to the start |
| `state()` | Returns `{ scene, title, cursor, progress, stepCount, activeStep, playing, done, reducedMotion, error }` |
| `scenes()` | Lists registered ids |

Nothing plays until the viewer presses Play. Switching tabs stops playback and resets the new scene. Arrow keys, Home and End move between tabs. The controls are ordinary buttons, so the keyboard reaches them with no extra shortcuts.

## Respect reduced motion

Under `prefers-reduced-motion: reduce` the player never tweens. Play calls `draw(1, ctx)` once per step and holds each result for at least 2.5 seconds. Step, Back and the step list work as usual, and a notice explains the behaviour. Scenes need no code for this, provided they follow the drawing contract.

## Test a scene

Load `file://.../docs/visuals/motion/index.html` in Playwright. For each tab, check these points:

- `VconMotion.scenes()` lists the id and `VconMotion.state().error` stays `null`.
- `VconMotion.seek(stepCount)` reaches `done`, and the frame matches the frame after a full `play()`.
- No request leaves `file://`, and the console stays free of errors.
- With `reducedMotion: 'reduce'` set on the browser context, `play()` still reaches `done`.

## Keep the font licences

`fonts/` holds byte copies of Anton and the Inter variable font. Both use the SIL Open Font License 1.1, and each file carries its copyright and licence in its name table. Keep the files unmodified. Inter Italic is left out because nothing here sets italic text.
