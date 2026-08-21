// Shared TypeScript types for the CellScope frontend

export interface CalibrationInfo {
  source: 'ome_tiff_metadata' | 'user_provided' | 'unavailable'
  pixel_size_um: number | null
  calibrated: boolean
}

export interface CellInstance {
  cell_id: number
  area_px: number
  area_um2: number | null
  circularity: number
  centroid_y: number
  centroid_x: number
  mean_intensity: number
}

export interface Morphology {
  mean_area_px: number
  mean_area_um2: number | null
  std_area_px: number
  std_area_um2: number | null
  mean_circularity: number
  mean_intensity: number
  density_cells_per_mm2: number | null
}

export interface AnalysisResult {
  analysis_id: string
  cell_count: number
  morphology: Morphology
  cells: CellInstance[]
  calibration: CalibrationInfo
  segmentation_mask_b64: string
  annotated_image_b64: string
  inference_engine: string
  inference_time_ms: number
  model_version: string
  cache_hit: boolean
}

export interface AuditRow {
  id: string
  created_at: string
  cell_count: number
  mean_area_px: number
  mean_area_um2: number | null
  mean_circularity: number
  calibrated: number
  pixel_size_um: number | null
  calibration_source: string
  inference_engine: string
  inference_time_ms: number
  model_version: string
  cache_hit: number
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  model_version: string
  engine: string
  timestamp: string
}
