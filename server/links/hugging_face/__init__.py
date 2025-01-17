from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

logger = init_logger(__name__)

default_options = {
    "model_path": None,  # Must be configured in config.yml
    "max_tokens": 2000,
    "temperature": 0.7,
    "top_p": 0.95,
    "context_window": 4096,
    "n_gpu_layers": -1,  # Automatically use all layers that fit on GPU
    "prompt_template": "Below is a conversation transcript. Please analyze it:\n\n{text}\n\nAnalysis:",
}


def setup_model(model_name, token=None):
    # Load the specified model
    logger.info(f"Loading tokenizer and model for {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)
    return tokenizer, model


def generate_completion(prompt, tokenizer, model, max_length=200):
    # Format the prompt for chat
    chat_format = f"<|system|>You are a helpful AI assistant.<|user|>{prompt}<|assistant|>"

    # Prepare the input text
    inputs = tokenizer(chat_format, return_tensors="pt")

    # Generate text
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_length=max_length,
            num_return_sequences=1,
            temperature=0.7,
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    # Decode and clean up the generated text
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Remove the system and user prompts to get just the assistant's response
    response = generated_text.split("<|assistant|>")[-1].strip()
    return response


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    logger.info("Starting llama_link plugin for vCon: %s", vcon_uuid)

    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    # Initialize Hugging Face model and tokenizer
    try:
        tokenizer, model = setup_model(opts["model_path"])
    except Exception as e:
        logger.error("Failed to initialize Hugging Face model: %s", e)
        return vcon_uuid

    for index, dialog in enumerate(vCon.dialog):
        # Skip if not a transcript
        if "transcript" not in dialog.get("type", "").lower():
            continue

        # Get the transcript text
        text = dialog.get("body", {}).get("text", "")
        if not text:
            logger.info(
                "llama_link plugin: skipping empty transcript in dialog %s for vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        # Check if analysis already exists
        analysis_exists = False
        for analysis in vCon.analysis:
            if analysis.get("dialog") == index and analysis.get("vendor") == "huggingface_transformers":
                analysis_exists = True
                break

        if analysis_exists:
            logger.info(
                "Dialog %s already analyzed by huggingface_transformers in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        # Prepare prompt
        prompt = opts["prompt_template"].format(text=text)

        try:
            # Generate analysis
            analysis_text = generate_completion(prompt, tokenizer, model, max_length=opts["max_tokens"])

            # Add analysis to vCon
            vCon.add_analysis(
                type="llm_analysis",
                dialog=index,
                vendor="huggingface_transformers",
                body=analysis_text,
                extra={
                    "vendor_schema": {
                        "model": opts["model_path"].split("/")[-1],
                        "prompt_template": opts["prompt_template"],
                        "temperature": opts["temperature"],
                        "max_tokens": opts["max_tokens"],
                        "top_p": opts["top_p"],
                    }
                },
            )

            logger.info(
                "Successfully added Hugging Face analysis for dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )

        except Exception as e:
            logger.error(
                "Failed to generate analysis for dialog %s in vCon %s: %s",
                index,
                vCon.uuid,
                e,
            )
            continue

    # Store updated vCon
    vcon_redis.store_vcon(vCon)

    logger.info("Finished llama_link plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
