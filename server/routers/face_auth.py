import os
import base64
import logging
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from deepface import DeepFace

from utils.logger import api_logger as logger

router = APIRouter(prefix="/api/face-auth", tags=["Face Auth"])

# Directory to store face data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
MASTER_FACE_PATH = os.path.join(DATA_DIR, "master_face.jpg")

# ── Model config ──────────────────────────────────────────────────────────────
# Facenet512 is more accurate than VGG-Face (default).
# Its cosine threshold is 0.30 which means stricter matching.
# We tighten it further to 0.25 — only a very close match passes.
FACE_MODEL    = "Facenet512"
FACE_METRIC   = "cosine"
FACE_THRESHOLD = 0.25   # tighter than Facenet512's default of 0.30


class FaceImage(BaseModel):
    image_base64: str


def _decode_base64_image(image_base64: str) -> bytes:
    """Strip optional data-URL header and decode base64 to raw bytes."""
    if "," in image_base64:
        _, encoded = image_base64.split(",", 1)
    else:
        encoded = image_base64
    encoded += "=" * (-len(encoded) % 4)  # fix missing padding
    return base64.b64decode(encoded)


def _write_temp_image(image_data: bytes) -> str:
    """Write bytes to a unique temp file and return its path."""
    path = os.path.join(DATA_DIR, f"_tmp_{uuid.uuid4().hex}.jpg")
    with open(path, "wb") as f:
        f.write(image_data)
    return path


@router.get("/status")
def get_status():
    """Check if a master face is registered."""
    return {"registered": os.path.exists(MASTER_FACE_PATH)}


@router.post("/register")
def register_face(data: FaceImage):
    """
    Save the provided face image as the master face for this device.

    Steps:
      1. Decode base64 → JPEG bytes
      2. Detect face with strict enforcement (must contain a real face)
      3. Save as master_face.jpg
    """
    try:
        image_data = _decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    if len(image_data) < 1000:
        raise HTTPException(status_code=400, detail="Image is too small. Please try again.")

    tmp_path = _write_temp_image(image_data)

    try:
        # Enforce that a real face is present — reject images with no detectable face
        faces = DeepFace.extract_faces(
            tmp_path,
            enforce_detection=True,   # STRICT: raises FaceNotDetected if no face
            detector_backend="opencv",
        )
        if not faces:
            raise ValueError("No face detected")

        best_confidence = max(f.get("confidence", 0) for f in faces)
        logger.info("Registration face confidence: %.3f (faces found: %d)", best_confidence, len(faces))

        if best_confidence < 0.80:
            raise HTTPException(
                status_code=400,
                detail=f"Face not clearly visible (confidence {best_confidence:.0%}). "
                       "Please improve lighting and look directly at the camera."
            )

        # Promote temp file to master
        os.replace(tmp_path, MASTER_FACE_PATH)
        logger.info("Master face registered at %s", MASTER_FACE_PATH)
        return {"success": True, "message": "Face registered successfully"}

    except HTTPException:
        raise
    except ValueError as e:
        # FaceNotDetected is a ValueError subclass
        _cleanup(tmp_path)
        raise HTTPException(
            status_code=400,
            detail="No face detected in the photo. Please look directly at the camera in good lighting."
        )
    except Exception as e:
        _cleanup(tmp_path)
        logger.error("Registration error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Could not process image: {e}")


@router.post("/verify")
def verify_face(data: FaceImage):
    """
    Verify a captured face against the registered master face.

    Steps:
      1. Decode base64 → JPEG bytes
      2. STRICT face detection on the incoming image (must have a real face)
      3. Compare against master using Facenet512 with a tight threshold (0.25)
    """
    if not os.path.exists(MASTER_FACE_PATH):
        raise HTTPException(status_code=400, detail="No face registered yet. Please register first.")

    try:
        image_data = _decode_base64_image(data.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    tmp_path = _write_temp_image(image_data)

    try:
        # ── Step 1: Confirm a real face is present in the verification image ──
        try:
            faces = DeepFace.extract_faces(
                tmp_path,
                enforce_detection=True,   # STRICT
                detector_backend="opencv",
            )
            if not faces:
                raise ValueError("No face detected")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="No face detected in the photo. Please look directly at the camera."
            )

        # ── Step 2: Compare against the registered master face ─────────────────
        result = DeepFace.verify(
            img1_path=tmp_path,
            img2_path=MASTER_FACE_PATH,
            model_name=FACE_MODEL,
            distance_metric=FACE_METRIC,
            enforce_detection=True,    # STRICT: both images must have a detectable face
            threshold=FACE_THRESHOLD,  # custom tighter threshold
        )

        distance  = result.get("distance", 1.0)
        verified  = result.get("verified", False)
        threshold = result.get("threshold", FACE_THRESHOLD)

        logger.info(
            "Face verify | model=%s | distance=%.4f | threshold=%.4f | verified=%s",
            FACE_MODEL, distance, threshold, verified,
        )

        return {
            "success": True,
            "verified": bool(verified),
            "distance": round(distance, 4),
            "threshold": round(threshold, 4),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Verification error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")
    finally:
        _cleanup(tmp_path)


def _cleanup(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
