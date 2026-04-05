import os
import time
from urllib.parse import unquote, urlparse

from google import genai
from google.genai import types
from PIL import Image
from PIL.ImageFile import ImageFile

from tg_summary_core.config import settings
from tg_summary_core.report.text_cat import convert_item_to_json_text
from tg_summary_core.utils.common import clean_files, download_file

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


current_directory = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_DIR = os.path.join(current_directory, "..", "..", "download")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

remove_file_path_list: list[str] = []


def generate_gemini_parts_by_group_messages(group_messages: list) -> list:
    gemini_parts = []
    for message in group_messages:
        message_json_text = convert_item_to_json_text(message)
        gemini_parts.append(message_json_text)
        if message.get("media"):
            valid_media = resolve_message_media(message.get("media"))
            if valid_media:
                gemini_parts.append(valid_media)
    wait_until_all_parts_active(gemini_parts)
    clean_files(remove_file_path_list)
    return gemini_parts


def resolve_message_media(media: dict) -> ImageFile | types.File:
    result = None
    # download the file to your disk
    urlparser = urlparse(media["presignedUrl"])
    path = urlparser.path
    filename = os.path.basename(unquote(path))  # get the filename from s3 presigned url
    file_path = os.path.join(DEFAULT_DOWNLOAD_DIR, filename)
    if download_file(media["presignedUrl"], file_path):
        if media.get("mediaType") == "photo":  # use pillow to open the image files
            image = Image.open(file_path)
            result = image
        elif media.get("mediaType") == "video":  # upload video to google
            uploaded_file = upload_video_to_gemini(file_path)
            if uploaded_file:
                result = uploaded_file
    # clean the downloaded media files
    if os.path.exists(file_path):
        remove_file_path_list.append(file_path)
    if result:
        return result


def wait_until_all_parts_active(gemini_parts: list, timeout_seconds: int = 600, poll_interval_seconds: int = 10):
    """
    Waits for all uploaded `google.generativeai.types.File` objects in `gemini_parts`
    to become 'ACTIVE'.

    Args:
        gemini_parts: A list of parts that might contain genai.types.File objects.
        timeout_seconds: Maximum time to wait for files to become active.
        poll_interval_seconds: How often to check the file status.

    Raises:
        TimeoutError: If any file does not become ACTIVE within the timeout.
        Exception: If there's an API error checking file status or a file fails.
    """
    uploaded_files_to_check = [part for part in gemini_parts if isinstance(part, types.File)]

    if not uploaded_files_to_check:
        return  # No uploaded files to wait for

    print(f"Waiting for {len(uploaded_files_to_check)} uploaded file(s) to become ACTIVE...")
    start_time = time.time()

    while True:
        all_active = True
        for uploaded_file in uploaded_files_to_check:
            if uploaded_file.name is None:
                print(f"Warning: uploaded file has no name, skipping status check: {uploaded_file}")
                continue
            try:
                # Retrieve the file status from the Gemini API
                file_status = _get_client().files.get(name=uploaded_file.name)
                print(f"File '{file_status.display_name}' ({file_status.name}) status: {file_status.state}")

                if file_status.state == types.FileState.ACTIVE:
                    continue  # This file is ready
                elif file_status.state == types.FileState.FAILED:
                    raise Exception(
                        f"File '{file_status.display_name}' ({file_status.name}) "
                        f"failed to process with state: {file_status.state}"
                    )
                else:
                    all_active = False  # Keep waiting for this one

            except Exception as e:
                # Catch any API errors during status check
                print(f"Error checking status for file {uploaded_file.name}: {e}")
                raise  # Re-raise the exception to indicate a critical failure

        if all_active:
            print("All uploaded files are ACTIVE.")
            break  # Exit the loop, all files are ready

        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Timeout waiting for uploaded files to become ACTIVE after {timeout_seconds} seconds.")

        time.sleep(poll_interval_seconds)


def generate_gemini_response_by_gemini_parts(
    gemini_parts: list, model: str = None, seed: int | None = None, temperature: float = 1
) -> str:
    """
    Generate a response from Gemini using the provided parts.

    Args:
        temperature: Sampling temperature for generation
        gemini_parts: List of parts to send to Gemini (text, images, videos, etc.)
        model: The Gemini model to use
        seed: Optional random seed for deterministic generation

    Returns:
        The generated text response
    """
    if model is None:
        model = settings.default_gemini_model

    config = types.GenerateContentConfig(candidate_count=1, seed=seed, temperature=temperature)

    processed_gemini_parts = count_token_and_remove(gemini_parts, model)

    try:
        response = _get_client().models.generate_content(model=model, contents=processed_gemini_parts, config=config)
        return response.text
    except Exception as e:
        print(f"Error generating content: {e}")
        return f"Error: {str(e)}"


def count_token_and_remove(gemini_parts: list, model: str) -> list:
    result_list = []
    for content in gemini_parts:
        if not content:
            continue
        try:
            count_resp = _get_client().models.count_tokens(model=model, contents=[content])
            input_token = count_resp.total_tokens
            if input_token > 200000:  # if above it, remove it from the list
                continue
            else:
                result_list.append(content)
        except Exception as e:
            print(f"Error counting tokens: {e}")
            result_list.append(content)
    return result_list


def generate_gemini_response(prompt: str, model: str = None, seed: int | None = None, temperature: float = 1) -> str:
    """
    Generate a response from Gemini using a text prompt.

    Args:
        temperature: Sampling temperature for generation
        prompt: The text prompt to send
        model: The Gemini model to use
        seed: Optional random seed for deterministic generation

    Returns:
        The generated text response
    """
    if model is None:
        model = settings.default_gemini_model

    config = types.GenerateContentConfig(seed=seed, temperature=temperature)

    try:
        response = _get_client().models.generate_content(model=model, contents=prompt, config=config)

        if not response.text:
            candidates = response.candidates
            if candidates:
                reason = candidates[0].finish_reason
                return f"AI response was blocked or empty. Finish reason: {reason}"
            return "AI response was empty."

        return response.text

    except Exception as e:
        print(f"Error generating content: {e}")
        return "An error occurred while processing the request."


def generate_gemini_response_multiple_seeds(
    gemini_parts: list,
    seeds: list[int],
    model: str = None,
    temperature: float = 1,
) -> list[str]:
    """
    Generate multiple responses from Gemini using different random seeds.

    Args:
        temperature: Sampling temperature for generation
        gemini_parts: List of parts to send to Gemini (text, images, videos, etc.)
        seeds: List of random seeds to use for generation
        model: The Gemini model to use

    Returns:
        List of generated text responses, one for each seed
    """
    results = []
    for i, seed in enumerate(seeds):
        print(f"Generating response with seed {seed} ({i + 1}/{len(seeds)})...")
        try:
            response = generate_gemini_response_by_gemini_parts(
                gemini_parts=gemini_parts, model=model, seed=seed, temperature=temperature
            )
            results.append(response)
        except Exception as e:
            print(f"Error generating response with seed {seed}: {e}")
            results.append(f"Error: {str(e)}")

    return results


def generate_gemini_response_multiple_times(
    gemini_parts: list, num_calls: int = 3, model: str = None, base_seed: int | None = None, temperature: float = 1
) -> list[str]:
    """
    Generate multiple responses from Gemini using different random seeds.

    Args:
        temperature:
        gemini_parts: List of parts to send to Gemini (text, images, videos, etc.)
        num_calls: Number of times to call the API (default: 3)
        model: The Gemini model to use
        base_seed: Optional base seed. If provided, seeds will be base_seed, base_seed+1, etc.
                   If not provided, seeds will be generated as 1, 2, 3, ...

    Returns:
        List of generated text responses
    """
    seeds = list(range(1, num_calls + 1)) if base_seed is None else [base_seed + i for i in range(num_calls)]

    return generate_gemini_response_multiple_seeds(
        gemini_parts=gemini_parts, seeds=seeds, model=model, temperature=temperature
    )


def upload_video_to_gemini(video_path: str):
    print(f"Uploading video: {video_path}...")
    try:
        video_file = _get_client().files.upload(file=video_path)
        print(f"Uploaded file '{video_file.display_name}' as: {video_file.name}")
        return video_file
    except Exception as e:
        print(f"Error uploading video {video_path}: {e}")
        return None
