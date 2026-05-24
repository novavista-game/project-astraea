import json
import math

class SentinelIngestionPipeline:
    def __init__(self):
        """
        Initializes the Sentinel-2 Ingestion Pipeline for Project Astraea.
        """
        # Bounding box expansion constant: approx 250m in degrees (1 degree lat ~= 111,000m)
        self.LAT_DEGREE_METER = 111139.0
        self.LON_DEGREE_METER = 111320.0 # Varies by latitude, calibrated at equator

    def compute_bounding_box(self, latitude, longitude, radius_meters=250.0):
        """
        Computes WGS 84 bounding box coordinates for Sentinel-2 search parameters.
        """
        delta_lat = radius_meters / self.LAT_DEGREE_METER
        # Adjust longitude delta based on latitude curvature
        rad_lat = math.radians(latitude)
        delta_lon = radius_meters / (self.LON_DEGREE_METER * math.cos(rad_lat))

        return {
            "min_lat": latitude - delta_lat,
            "max_lat": latitude + delta_lat,
            "min_lon": longitude - delta_lon,
            "max_lon": longitude + delta_lon
        }

    def fetch_multispectral_telemetry(self, bbox):
        """
        Simulates the retrieval of Sentinel-2 multispectral band data.
        In a deployed environment, this targets the Copernicus Sentinel Hub REST API.
        
        Returns raw reflectance values for targeted bands (scaled 0 to 10000):
        - B2: Blue (0.490 µm)
        - B3: Green (0.560 µm)
        - B4: Red (0.665 µm)
        - B8: Near-Infrared / NIR (0.842 µm)
        - B11: Shortwave Infrared / SWIR-1 (1.610 µm)
        - B12: Shortwave Infrared / SWIR-2 (2.190 µm)
        """
        # Determine simulation variables based on bounding box location to represent Kibera (urban/dense)
        is_dense_urban = bbox["min_lat"] < 0.0 and (36.7 <= bbox["min_lon"] <= 36.8)

        if is_dense_urban:
            # High urban density signature: high SWIR reflectance, low NIR (vegetation), moderate red
            return {
                "B2": 1500, # Blue
                "B3": 1800, # Green
                "B4": 2200, # Red
                "B8": 2400, # NIR
                "B11": 4200, # SWIR-1
                "B12": 3900  # SWIR-2
            }
        else:
            # Vegetation-heavy signature (rural/forest): low red, very high NIR, low SWIR
            return {
                "B2": 800,
                "B3": 1200,
                "B4": 900,
                "B8": 6800,
                "B11": 1500,
                "B12": 1000
            }

    def calculate_spectral_indices(self, bands):
        """
        Calculates environmental and built-up indices from raw bands:
        1. NDVI (Normalized Difference Vegetation Index) = (B8 - B4) / (B8 + B4)
        2. NDBI (Normalized Difference Built-Up Index) = (B11 - B8) / (B11 + B8)
        3. BUI (Built-Up Index) = NDBI - NDVI
        """
        b4 = float(bands["B4"])
        b8 = float(bands["B8"])
        b11 = float(bands["B11"])

        # Prevent division by zero
        ndvi_denom = b8 + b4
        ndvi = (b8 - b4) / ndvi_denom if ndvi_denom != 0 else 0.0

        ndbi_denom = b11 + b8
        ndbi = (b11 - b8) / ndbi_denom if ndbi_denom != 0 else 0.0

        # BUI acts as a proxy for concrete/steel urban structures vs natural biomass
        bui = ndbi - ndvi

        return {
            "ndvi": round(ndvi, 4),
            "ndbi": round(ndbi, 4),
            "built_up_index": round(bui, 4)
        }

    def process_spatial_ingress(self, latitude, longitude):
        """
        Ingests user coordinates and computes the spatial validation matrix.
        """
        # Validate coordinates bounds
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            raise ValueError("Coordinates exceed valid global limits.")

        bbox = self.compute_bounding_box(latitude, longitude)
        bands = self.fetch_multispectral_telemetry(bbox)
        indices = self.calculate_spectral_indices(bands)

        # Classification heuristics for validation pipeline
        is_built_up = indices["built_up_index"] > -0.10
        vegetation_density = "HIGH" if indices["ndvi"] > 0.40 else ("MEDIUM" if indices["ndvi"] > 0.15 else "LOW")

        return {
            "input_coordinates": {
                "latitude": latitude,
                "longitude": longitude
            },
            "geospatial_bounds": bbox,
            "spectral_data": bands,
            "environmental_indices": indices,
            "classification": {
                "urban_structure_confirmed": is_built_up,
                "vegetation_density": vegetation_density
            }
        }

if __name__ == "__main__":
    print("Initializing Sentinel-2 Ingestion Pipeline Verification Routine...")
    pipeline = SentinelIngestionPipeline()

    # Case A: Kibera Settlement Coordinates (-1.312948, 36.790214)
    kibera_lat, kibera_lon = -1.312948, 36.790214
    kibera_output = pipeline.process_spatial_ingress(kibera_lat, kibera_lon)
    print("\n--- TEST CASE A: Kibera (Dense Urban Settlement) ---")
    print(json.dumps(kibera_output, indent=2))
    assert kibera_output["classification"]["urban_structure_confirmed"] is True, "Kibera detection failed."

    # Case B: Rural forest region (e.g. Kakamega Forest, Kenya)
    forest_lat, forest_lon = 0.2828, 34.8624
    forest_output = pipeline.process_spatial_ingress(forest_lat, forest_lon)
    print("\n--- TEST CASE B: Rural Forest (Vegetation-Heavy) ---")
    print(json.dumps(forest_output, indent=2))
    assert forest_output["classification"]["urban_structure_confirmed"] is False, "Forest detection failed."

    print("\n[PASSED] Ingestion pipeline index logic and classification filters verified.")
