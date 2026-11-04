# transcribe

The single entry point for speech to text. It hands the vCon to the vendor named in its options.

Module: `links.transcribe`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `vendor` | string | `whisper_builtin` | `openai`, `groq`, `hugging_face`, `deepgram` or `whisper_builtin` |
| `vendor_options` | dict | `{"model_size": "base", "output_options": ["vendor"]}` | Passed unchanged to the vendor. The default suits `whisper_builtin` only |
| `transcribe_options` | dict | none | Legacy name for `vendor_options`, used when `vendor_options` is absent |

Each vendor reads its own options inside `vendor_options`.

| `vendor` | Implementation | Options |
|---|---|---|
| `openai` | `links.openai_transcribe` | [openai_transcribe](openai-transcribe.md#set-the-options) |
| `groq` | `links.groq_whisper` | [groq_whisper](groq-whisper.md#set-the-options) |
| `hugging_face` | `links.hugging_face_whisper` | [hugging_face_whisper](huggingface-whisper.md#set-the-options) |
| `deepgram` | `links.deepgram_link` | [deepgram_link](deepgram.md#set-the-options) |
| `whisper_builtin` | `Vcon.transcribe()` | See the known issue below |

Always set `vendor_options` when you name a vendor. Without it the vendor receives the `whisper_builtin` defaults and no credentials.

WTF transcripts have their own link, [wtf_transcribe](wtf-transcribe.md), because they use a different analysis schema.

## Follow the processing steps

1. Merge the options and resolve the vendor. An empty `vendor` means `whisper_builtin`.
2. Pick `vendor_options`, then `transcribe_options`, then the default.
3. Import the vendor module and call its `run` with those options. An unknown vendor raises `ValueError`.

Vendors act only on dialogs with `type` of `recording`. A vCon with none passes through unchanged and counts as a success. See [transcribe a recording](../../configuration/chains-and-pipelines.md#transcribe-a-recording).

The worker also sends the deprecated modules here. A chain entry of `module: links.groq_whisper` becomes `links.transcribe` with `vendor: groq` and logs one deprecation warning per module. Its existing options block becomes `vendor_options`.

## Check the known issues

`whisper_builtin` is the default vendor and does not work in the server image. It calls `vCon.transcribe()`, and the `Vcon` class in `common/vcon.py`, which is the class the worker imports, has no such method. The link raises `AttributeError` and the vCon goes to the dead letter queue. Always set `vendor` to one of the other four.

## Read the return value

The vendor's return value. With `whisper_builtin`, `None` when the vCon is missing.

## Inspect the vCon changes

See the vendor's page. Each one adds analysis of type `transcript`. The body differs by vendor, which matters for [the links that read it](index.md#point-analysis-at-the-transcript-text).

## Copy a configuration example

```yaml
links:
  transcribe_openai:
    module: links.transcribe
    options:
      vendor: openai
      vendor_options:
        OPENAI_API_KEY: your-openai-key
        model: gpt-4o-transcribe
        minimum_duration: 3
```

## Track the metrics

The dispatcher emits none of its own. See the vendor's page.
