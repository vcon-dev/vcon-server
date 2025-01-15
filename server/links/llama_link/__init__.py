from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from llama_cpp import Llama

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

    # Initialize Llama model
    try:
        llm = Llama(model_path=opts["model_path"], n_ctx=opts["context_window"], n_gpu_layers=opts["n_gpu_layers"])
    except Exception as e:
        logger.error("Failed to initialize Llama model: %s", e)
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
            if analysis.get("dialog") == index and analysis.get("vendor") == "llama_cpp":
                analysis_exists = True
                break

        if analysis_exists:
            logger.info(
                "Dialog %s already analyzed by llama_cpp in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        # Prepare prompt
        prompt = opts["prompt_template"].format(text=text)

        try:
            # Generate analysis
            response = llm(
                prompt, max_tokens=opts["max_tokens"], temperature=opts["temperature"], top_p=opts["top_p"], echo=False
            )

            analysis_text = response["choices"][0]["text"].strip()

            # Add analysis to vCon
            vCon.add_analysis(
                type="llm_analysis",
                dialog=index,
                vendor="llama_cpp",
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
                "Successfully added llama_cpp analysis for dialog %s in vCon: %s",
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
