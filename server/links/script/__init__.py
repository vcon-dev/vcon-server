from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import openai
from settings import OPENAI_API_KEY
import traceback
openai.api_key = OPENAI_API_KEY

logger = init_logger(__name__)

default_options = {
    "model": "gpt-4o",
    "prompt": "Rewrite this transcript into speakers, speaking like they are from Boston : ",
}


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    logger.debug("Starting script::run")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    # Find the transcript, if it exists.
    transcripts = vCon.get_transcripts()
    try:
        for transcript, dialog_index in transcripts:
            # This can fail if the transcript is too long.
            robot_prompt = opts["prompt"] + transcript
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": robot_prompt + "\n\n" + transcript},
            ]
            rewrite_result = openai.ChatCompletion.create(
                model=opts["model"],
                messages=messages,
                temperature=0,
            )
            script = rewrite_result["choices"][0]["message"]["content"]
            vCon.add_analysis(
                dialog=dialog_index, type="script", body=script, vendor="openai", extra=opts["prompt"]
            )
    except Exception as ex:
        logger.error("Failed to rewrite transcript: %s", ex)
        traceback.print_exc()  # noqa F821
    # TODO: Add new mime type for script (text/plain)

    logger.info("Script added to vCon: %s", vCon.uuid)

    vcon_redis.store_vcon(vCon)

    # Return the vcon_uuid down the chain.
    # If you want the vCon processing to stop (if you are filtering them, for instance)
    # send None
    return vcon_uuid
