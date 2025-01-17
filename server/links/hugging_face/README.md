# Llama Link

The Llama Link is a conserver link that uses [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) to run local LLM inference on conversation transcripts. This link allows you to analyze conversations using any GGUF model compatible with llama.cpp, without requiring external API access.

## Features

- Local LLM inference using llama.cpp
- Configurable model parameters
- GPU acceleration support
- Customizable prompt templates
- Automatic transcript analysis

## Prerequisites

- Python 3.7+
- llama-cpp-python package
- A GGUF model file (e.g., from [TheBloke's models](https://huggingface.co/TheBloke))

## Installation

1. Install the required dependencies:

```bash
pip install llama-cpp-python
```

For GPU support (recommended), install with CUDA:

```bash
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

2. Download a GGUF model file and place it in an accessible location.

## Configuration

Add the following configuration to your conserver configuration file (`config.yml`):

```yaml
links:
  llama:
    module: links.llama_link
    options:
      model_path: "/path/to/your/model.gguf"  # Required: Path to your GGUF model file
      max_tokens: 2000                         # Optional: Maximum tokens in response
      temperature: 0.7                         # Optional: Temperature for sampling
      top_p: 0.95                             # Optional: Top-p sampling parameter
      context_window: 4096                     # Optional: Context window size
      n_gpu_layers: -1                        # Optional: Number of layers to offload to GPU (-1 for auto)
      prompt_template: "..."                   # Optional: Custom prompt template
```

### Configuration Options

- `model_path` (required): Path to your GGUF model file
- `max_tokens` (optional, default: 2000): Maximum number of tokens in the generated response
- `temperature` (optional, default: 0.7): Controls randomness in generation
- `top_p` (optional, default: 0.95): Controls diversity via nucleus sampling
- `context_window` (optional, default: 4096): Size of the context window in tokens
- `n_gpu_layers` (optional, default: -1): Number of layers to offload to GPU
- `prompt_template` (optional): Custom prompt template for analysis

## Usage

The Llama Link will automatically process transcripts in vCons as they pass through the conserver. For each transcript, it will:

1. Load the specified GGUF model
2. Format the transcript using the prompt template
3. Generate an analysis using the local LLM
4. Add the analysis to the vCon with metadata

### Chain Configuration Example

```yaml
chains:
  analyze_chain:
    links:
      - transcribe
      - llama
    ingress_lists:
      - analyze_ingress
    egress_lists:
      - default_egress
    enabled: 1
```

## Troubleshooting

- If you encounter GPU memory issues, try reducing `n_gpu_layers` or using a smaller model
- If the analysis is too short, try increasing `max_tokens`
- If the analysis quality is poor, try:
  - Adjusting the temperature and top_p values
  - Using a different model
  - Modifying the prompt template

## License

The Llama Link is open-sourced under the MIT license. 