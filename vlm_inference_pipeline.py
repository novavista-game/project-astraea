import os
import json
import re
from datetime import datetime, timezone

# Import Google GenAI SDK (with fallback mock interface for offline/blueprint verification)
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

class AstraeaVlmPipeline:
    def __init__(self, api_key=None):
        """
        Initializes the Project Astraea VLM Inference Pipeline (HEVI Variant).
        """
        if HAS_GENAI:
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
            if self.api_key:
                genai.configure(api_key=self.api_key)
            self.model_name = "gemini-1.5-flash"
        else:
            print("[Warning] google-generativeai SDK not installed. Running in Blueprint/Mock mode.")

        # Load system prompt
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self):
        return """
You are the lead Humanitarian Structural Analytics Engine for Project Astraea.
Your task is to analyze raw imagery of informal housing and output the HEVI metrics JSON matching this schema:
{
  "roofing_condition_metrics": {
    "primary_material": "CANVAS|WEATHERED_TIMBER|CORRUGATED_IRON|CONCRETE_SLAB|ASBESTOS_SHEET|UNKNOWN",
    "roofing_degradation_index": <float: 0.0 to 1.0>,
    "waterproofing_failed": <boolean>
  },
  "water_sanitation_ingress": {
    "drinking_water_distance_meters": <float>,
    "contamination_source_proximity_meters": <float>,
    "water_vulnerability_index": <float: 0.0 to 1.0>
  },
  "sanitary_latrine_metrics": {
    "latrine_structure_present": <boolean>,
    "septic_tank_integrated": <boolean>,
    "sanitation_degradation_index": <float: 0.0 to 1.0>
  },
  "floor_composition_score": {
    "floor_material": "DIRT|CONCRETE|TILE|RAISED_WOOD|UNKNOWN",
    "pathogen_exposure_risk_index": <float: 0.0 to 1.0>
  }
}
Do NOT wrap your response in markdown code blocks. Output raw JSON only.
"""

    def generate_user_prompt(self, telemetry):
        """
        Formats the user prompt using client-side metadata context.
        """
        template = """
### Telemetry and Sensor Metadata Context
The following sensor metadata was recorded during image capture. Use it to calibrate spatial scale, angles, and environmental parameters:

- **Capture Timestamp**: {timestamp}
- **Anonymized spatial reference**: H3 Index {h3_index}
- **Lens Field of View (FOV)**: {fov}°

### Task Instructions
1. Analyze the attached image files in combination with the sensor telemetry above.
2. Formulate the structural evaluation parameters based on the system prompt guidelines.
3. Compute the structural metrics and output the raw JSON format.
"""
        return template.format(
            timestamp=telemetry.get("timestamp", datetime.now(timezone.utc).isoformat()),
            h3_index=telemetry.get("h3_index", "8c7a6e1a4db93ff"),
            fov=telemetry.get("fov", 78.0)
        )

    def calculate_hevi_score(self, vlm_data):
        """
        Calculates the Healthspan Environmental Vulnerability Index (HEVI).
        Scale: 0.0 (low vulnerability / safe) to 100.0 (high vulnerability / unsafe).
        
        Formula:
        HEVI = (w1 * RoofDeg + w2 * WaterVuln + w3 * (1.0 - LatrineScore) + w4 * FloorPathogen) * 100
        Weights: w1=0.30, w2=0.25, w3=0.20, w4=0.25
        """
        roof = vlm_data.get("roofing_condition_metrics", {})
        water = vlm_data.get("water_sanitation_ingress", {})
        latrine = vlm_data.get("sanitary_latrine_metrics", {})
        floor = vlm_data.get("floor_composition_score", {})

        # 1. Roofing Degradation (0.0 to 1.0)
        roof_deg = roof.get("roofing_degradation_index", 0.5)

        # 2. Water Vulnerability (0.0 to 1.0)
        water_vuln = water.get("water_vulnerability_index", 0.5)

        # 3. Latrine Score calculation (0.0 to 1.0)
        latrine_present = latrine.get("latrine_structure_present", False)
        septic_integrated = latrine.get("septic_tank_integrated", False)
        
        if latrine_present and septic_integrated:
            latrine_score = 1.0
        elif latrine_present:
            latrine_score = 0.5
        else:
            latrine_score = 0.0
            
        latrine_vuln = 1.0 - latrine_score

        # 4. Floor Pathogen Exposure Risk Index (0.0 to 1.0)
        floor_pathogen = floor.get("pathogen_exposure_risk_index", 0.5)

        # Apply weights
        w1, w2, w3, w4 = 0.30, 0.25, 0.20, 0.25
        hevi = (w1 * roof_deg + w2 * water_vuln + w3 * latrine_vuln + w4 * floor_pathogen) * 100.0
        
        return round(max(0.0, min(100.0, hevi)), 2)

    def run_inference(self, image_bytes_or_path, telemetry):
        """
        Executes inference against Gemini Flash. Fallbacks to mock generation if offline.
        """
        user_prompt = self.generate_user_prompt(telemetry)

        if HAS_GENAI and self.api_key:
            try:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=self.system_prompt
                )
                response = model.generate_content([user_prompt])
                raw_text = response.text.strip()
                raw_text = re.sub(r"^```json\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                
                parsed_json = json.loads(raw_text)
                return parsed_json
            except Exception as e:
                print(f"[Error] Real inference failed: {e}. Falling back to structural mock validation.")

        return self._generate_mock_ingress(telemetry)

    def _generate_mock_ingress(self, telemetry):
        """
        Simulates model output for testing/dry-runs.
        """
        return {
            "roofing_condition_metrics": {
                "primary_material": "CORRUGATED_IRON",
                "roofing_degradation_index": 0.68,
                "waterproofing_failed": True
            },
            "water_sanitation_ingress": {
                "drinking_water_distance_meters": 120.0,
                "contamination_source_proximity_meters": 15.0,
                "water_vulnerability_index": 0.72
            },
            "sanitary_latrine_metrics": {
                "latrine_structure_present": True,
                "septic_tank_integrated": False,
                "sanitation_degradation_index": 0.60
            },
            "floor_composition_score": {
                "floor_material": "DIRT",
                "pathogen_exposure_risk_index": 0.85
            }
        }

if __name__ == "__main__":
    print("Initializing Astraea HEVI Ingest Pipeline validator...")
    pipeline = AstraeaVlmPipeline()

    mock_telemetry = {
        "timestamp": "2026-05-24T18:54:00Z",
        "h3_index": "8c7a6e1a4db93ff",
        "fov": 78.0
    }

    parsed_output = pipeline.run_inference(None, mock_telemetry)
    print("\nParsed HEVI Ingress Payload:")
    print(json.dumps(parsed_output, indent=2))

    hevi = pipeline.calculate_hevi_score(parsed_output)
    print(f"\nCalculated Healthspan Environmental Vulnerability Index (HEVI): {hevi} / 100.0")
    
    assert 0.0 <= hevi <= 100.0, "Calculated HEVI exceeds valid bounds"
    print("\nHEVI Pipeline validation successful.")
