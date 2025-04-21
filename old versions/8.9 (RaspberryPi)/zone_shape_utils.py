import numpy as np

def toggle_zone_shape(calibrator, zone_idx):
    """Toggle the shape of the zone at the given index between circle and rectangle."""
    if zone_idx is None or zone_idx >= len(calibrator.zones):
        return
    calibrator.undo_redo.save_state("toggle_shape", calibrator.zones)
    zone = calibrator.zones[zone_idx]
    if len(zone) == 4:  # Circle to Rectangle
        x, y, radius, points = zone
        side = int(np.sqrt(np.pi * radius**2))
        calibrator.zones[zone_idx] = [x - side//2, y - side//2, side, side, points]
    else:  # Rectangle to Circle
        x, y, w, h, points = zone
        radius = int(np.sqrt(w * h / np.pi))
        calibrator.zones[zone_idx] = [x + w//2, y + h//2, radius, points]
    calibrator.scoring_zones.save_zones()
    calibrator.manager.save_current_zone_set()
    print(f"Toggled shape for zone {zone_idx}")