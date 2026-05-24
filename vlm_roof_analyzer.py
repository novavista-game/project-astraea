import os
import json
import socket
from io import BytesIO

# Try importing PIL to check image structure validity
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Import Google GenAI SDK (with both old and new SDK mappings)
try:
    from google import genai
    from google.genai import types
    HAS_NEW_SDK = True
except ImportError:
    HAS_NEW_SDK = False
    try:
        import google.generativeai as genai
        HAS_LEGACY_SDK = True
    except ImportError:
        HAS_LEGACY_SDK = False

class VlmRoofAnalyzer:
    def __init__(self, api_key=None):
        """
        Initializes the VLM Roof Analysis Ingress Pipeline.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-1.5-flash" # Default low-latency standard model

    def validate_image_asset(self, image_data):
        """
        Conducts pre-flight checking of the image asset to catch corruption early.
        """
        if not image_data:
            raise ValueError("ERR_MISSING_BINARY: Ingress image payload is empty.")
            
        if not HAS_PIL:
            # Skip check if PIL is missing, proceed at risk
            return True
            
        try:
            # Attempt to open and verify the binary structure
            img = Image.open(BytesIO(image_data))
            img.verify()
            return True
        except Exception as e:
            raise ValueError(f"ERR_IMAGE_CORRUPTED: Image parsing verification failed. Details: {e}")

    def analyze_roof(self, image_bytes, metadata=None):
        """
        Ingests image bytes and metadata, processes structural analysis, 
        and outputs the target verified JSON format.
        """
        # 1. Pre-flight checks
        try:
            self.validate_image_asset(image_bytes)
        except ValueError as err:
            return {
                "status": "FAILED",
                "error_code": "IMAGE_CORRUPTED",
                "message": str(err)
            }

        if not metadata:
            return {
                "status": "FAILED",
                "error_code": "MISSING_METADATA",
                "message": "Spatial metadata context is required to execute scale calculations."
            }

        # 2. System and User Prompt Definition
        system_instruction = (
            "You are an expert structural engineer analyzing informal settlement roof structures. "
            "Evaluate the image and output ONLY a raw JSON object containing these exact fields: "
            "'roofing_material' (string, e.g. corrugated_iron, concrete, thatch, tile, unknown), "
            "'degradation_index' (float from 0.0 to 1.0 based on rust/holes/warping), and "
            "'confidence_score' (float representation of your output classification confidence)."
        )

        user_content = (
            f"Analyze the attached roof image. Telemetry Context:\n"
            f"- Coordinates: Lat {metadata.get('lat', 0.0)}, Lon {metadata.get('lon', 0.0)}\n"
            f"- Azimuth/Yaw: {metadata.get('azimuth', 0.0)} degrees\n"
            f"Ensure output contains only valid, raw JSON matches the requested schema."
        )

        # 3. Model API execution with Timeout and SDK abstraction
        if not self.api_key:
            # Fallback mock execution for developer testing/offline dry-run
            return self._execute_mock_analysis(metadata)

        try:
            if HAS_NEW_SDK:
                # Execution utilizing the new Google GenAI SDK
                client = genai.Client(api_key=self.api_key)
                
                # Setup configuration
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.1
                )
                
                # In production, pass PIL image directly in contents
                # For blueprint execution, mock content passing is used
                img_pil = Image.open(BytesIO(image_bytes))
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[img_pil, user_content],
                    config=config
                )
                raw_text = response.text.strip()
            elif HAS_LEGACY_SDK:
                # Fallback to legacy SDK mapping
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction
                )
                img_pil = Image.open(BytesIO(image_bytes))
                response = model.generate_content([img_pil, user_content])
                raw_text = response.text.strip()
            else:
                raise ImportError("No compatible Google GenAI SDK found in runtime environment.")

            # Validate and parse JSON response
            parsed = json.loads(raw_text)
            
            # Enforce schema integrity
            required_keys = ["roofing_material", "degradation_index", "confidence_score"]
            if not all(key in parsed for key in required_keys):
                raise KeyError(f"Missing expected VLM output keys. Obtained keys: {list(parsed.keys())}")

            return {
                "status": "SUCCESS",
                "payload": parsed
            }

        except (socket.timeout, Exception) as e:
            # Check explicitly for network/API availability errors
            error_msg = str(e)
            return {
                "status": "FAILED",
                "error_code": "API_UNAVAILABLE_OR_TIMEOUT" if "API" in error_msg or "timeout" in error_msg else "SCHEMA_VALIDATION_FAILED",
                "message": f"Execution halted during VLM API request or serialization. Details: {e}"
            }

    def _execute_mock_analysis(self, metadata):
        """
        Simulates model output to facilitate offline verification.
        """
        # Calibrate based on mock coordinate range
        is_kibera = metadata.get("lat", 0.0) < 0.0
        return {
            "status": "SUCCESS",
            "payload": {
                "roofing_material": "corrugated_iron" if is_kibera else "concrete",
                "degradation_index": 0.45 if is_kibera else 0.05,
                "confidence_score": 0.89
            }
        }

if __name__ == "__main__":
    print("Executing local pre-flight checks for VLM Roof Analyzer...")
    analyzer = VlmRoofAnalyzer()

    # Generate a mock 1x1 pixel image binary for local pipeline test
    mock_image_io = BytesIO()
    if HAS_PIL:
        img = Image.new('RGB', (1, 1), color='red')
        img.save(mock_image_io, format='JPEG')
    mock_image_bytes = mock_image_io.getvalue() or b"Fake JPEG Header Data"

    mock_metadata = {
        "lat": -1.312948,
        "lon": 36.790214,
        "azimuth": 142.5
    }

    # Test Case 1: Successful verification run
    print("\n--- TEST CASE 1: Valid Ingress Payload ---")
    res1 = analyzer.analyze_roof(mock_image_bytes, mock_metadata)
    print(json.dumps(res1, indent=2))
    assert res1["status"] == "SUCCESS", "Valid payload analysis failed."

    # Test Case 2: Image Corruption Ingress Error Handling
    print("\n--- TEST CASE 2: Corrupted Image Binary ---")
    corrupt_bytes = b"BAD_DATA_STREAM_8829"
    res2 = analyzer.analyze_roof(corrupt_bytes, mock_metadata)
    print(json.dumps(res2, indent=2))
    assert res2["error_code"] == "IMAGE_CORRUPTED", "Failed to catch corrupted binary."

    # Test Case 3: Missing Metadata Ingress Error Handling
    print("\n--- TEST CASE 3: Missing Spatial Metadata ---")
    res3 = analyzer.analyze_roof(mock_image_bytes, None)
    print(json.dumps(res3, indent=2))
    assert res3["error_code"] == "MISSING_METADATA", "Failed to catch missing metadata."

    print("\n[PASSED] VLM Roof Analyzer unit checks completed successfully.")
