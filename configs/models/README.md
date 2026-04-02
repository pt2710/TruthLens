# Models

Model metadata, registry declarations, calibration profiles, and the executable
architecture-layer roadmap belong here.

- `architecture_layers.json` is the versioned source of truth for which AI/ML
  components are implemented now versus still planned.
- `text_encoder.json` configures the requested text representation path and
  fallback behavior for the training/runtime text head.
- `vision_encoder.json` configures the requested thumbnail-encoder path and
  fallback behavior for the training/runtime vision head.
- `history_encoder.json` configures the requested temporal history encoder path
  and fallback behavior for the history head.
