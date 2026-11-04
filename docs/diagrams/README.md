# Diagram sources

This folder holds the Mermaid sources for the docs and the SVGs built from them.

The [visuals index](../visuals/index.md) lists D01 to D14 with their SVGs, owner pages and motion scenes.

## File names

Each diagram has three files:

- `Dnn-name.mmd`, the source
- `Dnn-name.svg`, the rendered output
- `Dnn.sources.md`, the code paths the diagram was drawn from

## Brand theme

The first line of every `.mmd` file must be the `%%{init}%%` line from `_init.txt`, copied exactly. `render_diagrams.sh` fails a diagram that does not start with it.

`vconic-theme.json` holds the same colours as a Mermaid config file. Change both files together.

| Role | Colour |
|---|---|
| Node border | `#0A7D18` |
| Node fill | `#F3F4F6` |
| Heading text | `#292929` |
| Body text and lines | `#33363B` |
| Secondary borders | `#8A8A8D` |

Use `#0BB81E` to pick out one element with a `classDef`. Diagram text uses Inter.

## Rendering

From the repo root:

```bash
scripts/docs/render_diagrams.sh
```

The script uses `$MMDC` when set and otherwise runs mermaid-cli through `npx`. Set `PUPPETEER_CONFIG` to pass a puppeteer config file, for example to name a local Chrome. Pass a folder as the first argument to render somewhere else.

`scripts/docs/check.sh` renders every diagram to a temp folder to catch syntax errors. It does not compare SVG bytes, so commit the SVG whenever you change a source.
