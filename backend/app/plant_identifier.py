"""
WOP Backend — Plant Identifier
Uses Google Gemini API to identify plants from photos
and return structured care information.
"""

import json
import logging
import base64
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models import PlantIdentification

logger = logging.getLogger("wop.plant_id")

# Prompt sent to Gemini along with the plant image
IDENTIFICATION_PROMPT = """You are a plant identification expert. Analyze this image of a plant and provide the following information in valid JSON format:

{
    "common_name": "the most common name for this plant",
    "scientific_name": "the scientific/botanical name",
    "ideal_moisture_min": <integer 0-100, minimum ideal soil moisture percentage>,
    "ideal_moisture_max": <integer 0-100, maximum ideal soil moisture percentage>,
    "ideal_humidity_min": <integer 0-100, minimum ideal air humidity percentage>,
    "ideal_humidity_max": <integer 0-100, maximum ideal air humidity percentage>,
    "light_preference": "e.g. 'bright indirect', 'full sun', 'low light', 'partial shade'",
    "watering_frequency": "e.g. 'every 2-3 days', 'once a week', 'when top inch is dry'",
    "care_notes": "A brief paragraph with key care tips for this plant."
}

Return ONLY the JSON object, no markdown formatting, no code blocks, no explanation."""


async def identify_plant(image_path: str) -> Optional[PlantIdentification]:
    """
    Send a plant image to Gemini API and return structured identification.

    Args:
        image_path: Path to the saved image file.

    Returns:
        PlantIdentification with care details, or None on failure.
    """
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — plant identification unavailable")
        return _fallback_identification()

    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)

        # Read the image file
        image_bytes = Path(image_path).read_bytes()

        # Determine MIME type
        suffix = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mime_type = mime_map.get(suffix, "image/jpeg")

        # Call Gemini with the image
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": IDENTIFICATION_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                            }
                        },
                    ],
                }
            ],
        )

        # Parse the response
        text = response.text.strip()

        # Clean up response — remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # Remove first line
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        data = json.loads(text)
        identification = PlantIdentification(**data)
        logger.info("Identified plant: %s (%s)", identification.common_name, identification.scientific_name)
        return identification

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Gemini response as JSON: %s", e)
        return _fallback_identification()
    except Exception as e:
        logger.error("Plant identification error: %s", e)
        return _fallback_identification()


def _fallback_identification() -> PlantIdentification:
    """Return a default identification when AI is unavailable."""
    return PlantIdentification(
        common_name="Unknown Plant",
        scientific_name=None,
        ideal_moisture_min=30,
        ideal_moisture_max=70,
        care_notes="AI identification unavailable. Please set GEMINI_API_KEY or fill in the details manually.",
    )
