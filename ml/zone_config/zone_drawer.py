"""
zone_drawer.py — Interactive Parking Zone Configuration Tool
=============================================================
Draw polygon zones on a sample frame using OpenCV mouse events.
Saves zone boundaries and metadata to config/zones.json.

Controls:
  LEFT CLICK    — add vertex to current polygon
  RIGHT CLICK   — remove last vertex
  ENTER / SPACE — finish current polygon (prompts for name/angle/type)
  N             — start a new polygon without finishing the current one
  D             — delete the last saved zone
  S             — save all zones and quit
  Q             — quit without saving

Usage:
    python ml/zone_config/zone_drawer.py --frame data/raw_images/sample.jpg
    python ml/zone_config/zone_drawer.py --frame data/raw_images/sample.jpg --load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("ERROR: opencv-python is required for zone_drawer.")
    print("Install with: pip install opencv-python")
    sys.exit(1)

# Import zone loader
_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parents[2]))
from ml.zone_config.zone_loader import ZoneConfig, ZoneLoader


# ── Colour palette ─────────────────────────────────────────────────────────────
ZONE_COLORS = {
    "parking_bay": (255, 150, 0),    # blue
    "fire_lane":   (0, 0, 220),      # red
    "walkway":     (0, 215, 255),    # yellow
}
IN_PROGRESS_COLOR = (255, 255, 255)  # white


# ── State ──────────────────────────────────────────────────────────────────────

class DrawerState:
    def __init__(self, base_frame: np.ndarray, existing_zones: List[ZoneConfig]) -> None:
        self.base_frame    = base_frame.copy()
        self.zones: List[ZoneConfig]             = existing_zones[:]
        self.current_pts: List[Tuple[int, int]]  = []
        self.mouse_pos: Optional[Tuple[int, int]] = None
        self.status_msg: str = ""

    def add_vertex(self, x: int, y: int) -> None:
        self.current_pts.append((x, y))

    def remove_last_vertex(self) -> None:
        if self.current_pts:
            self.current_pts.pop()

    def delete_last_zone(self) -> None:
        if self.zones:
            removed = self.zones.pop()
            print(f"[ZoneDrawer] Deleted zone: {removed.name}")

    def render(self) -> np.ndarray:
        """Compose the frame with all drawn zones and current polygon."""
        frame = self.base_frame.copy()

        # Draw completed zones
        for zone in self.zones:
            pts = np.array(zone.boundary_polygon, dtype=np.int32)
            color = ZONE_COLORS.get(zone.zone_type, (180, 180, 180))
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
            cv2.polylines(frame, [pts], True, color, 2)
            # Label
            cx = int(np.mean(pts[:, 0]))
            cy = int(np.mean(pts[:, 1]))
            cv2.putText(frame, zone.name, (cx - 40, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"{zone.zone_type} / {zone.expected_angle_degrees:.0f}°",
                        (cx - 40, cy + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

        # Draw in-progress polygon
        if self.current_pts:
            for i, pt in enumerate(self.current_pts):
                cv2.circle(frame, pt, 5, IN_PROGRESS_COLOR, -1)
                if i > 0:
                    cv2.line(frame, self.current_pts[i - 1], pt, IN_PROGRESS_COLOR, 2)
            # Line to mouse cursor
            if self.mouse_pos and len(self.current_pts) >= 1:
                cv2.line(frame, self.current_pts[-1], self.mouse_pos, (180, 180, 180), 1)
            # Close preview
            if len(self.current_pts) >= 3 and self.mouse_pos:
                cv2.line(frame, self.current_pts[0], self.mouse_pos, (180, 180, 180), 1)

        # HUD
        instructions = [
            "LEFT CLICK: add vertex  |  RIGHT CLICK: remove vertex",
            "ENTER: finish zone  |  D: delete last zone  |  S: save & quit  |  Q: quit",
            f"Zones saved: {len(self.zones)}  |  Vertices in progress: {len(self.current_pts)}",
        ]
        if self.status_msg:
            instructions.append(self.status_msg)

        for i, txt in enumerate(instructions):
            y = frame.shape[0] - 20 - i * 22
            cv2.putText(frame, txt, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        return frame


# ── Mouse callback ─────────────────────────────────────────────────────────────

def _make_mouse_callback(state: DrawerState):
    def callback(event, x, y, flags, param):
        state.mouse_pos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            state.add_vertex(x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            state.remove_last_vertex()
    return callback


# ── Zone prompt ────────────────────────────────────────────────────────────────

def _prompt_zone_info(n: int) -> Tuple[str, float, str]:
    """Prompt user in terminal for zone metadata."""
    print(f"\n--- Finish Zone #{n} ---")

    name = input(f"  Zone name (e.g. 'Bay A') [default: Zone-{n}]: ").strip()
    if not name:
        name = f"Zone-{n}"

    while True:
        angle_str = input("  Expected parking angle in degrees (0=parallel, 90=perpendicular) [default: 90]: ").strip()
        if not angle_str:
            angle = 90.0
            break
        try:
            angle = float(angle_str)
            break
        except ValueError:
            print("  Please enter a number.")

    print("  Zone type options:")
    print("    1 = parking_bay")
    print("    2 = fire_lane")
    print("    3 = walkway")
    while True:
        type_str = input("  Select type [default: 1]: ").strip() or "1"
        type_map = {"1": "parking_bay", "2": "fire_lane", "3": "walkway",
                    "parking_bay": "parking_bay", "fire_lane": "fire_lane", "walkway": "walkway"}
        if type_str in type_map:
            zone_type = type_map[type_str]
            break
        print("  Enter 1, 2, or 3.")

    return name, angle, zone_type


# ── Main drawing loop ──────────────────────────────────────────────────────────

def run_drawer(frame_path: str, config_path: str, load_existing: bool = False) -> None:
    # Load base frame
    frame = cv2.imread(frame_path)
    if frame is None:
        print(f"ERROR: Cannot read frame: {frame_path}")
        sys.exit(1)

    # Load existing zones if requested
    existing_zones: List[ZoneConfig] = []
    if load_existing:
        existing_zones = ZoneLoader.load(config_path)
        print(f"[ZoneDrawer] Loaded {len(existing_zones)} existing zones from {config_path}")

    state = DrawerState(frame, existing_zones)
    win_name = "Zone Drawer — Two-Wheeler Parking"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, _make_mouse_callback(state))

    print("\n[ZoneDrawer] Window opened.")
    print("[ZoneDrawer] Controls:")
    print("  LEFT CLICK  — add polygon vertex")
    print("  RIGHT CLICK — remove last vertex")
    print("  ENTER/SPACE — finish current zone (will prompt for name)")
    print("  D           — delete last finished zone")
    print("  S           — save zones and quit")
    print("  Q           — quit WITHOUT saving")

    saved = False
    zone_counter = len(existing_zones) + 1

    while True:
        display = state.render()
        cv2.imshow(win_name, display)
        key = cv2.waitKey(30) & 0xFF

        if key in (13, 32):  # ENTER or SPACE — finish zone
            if len(state.current_pts) < 3:
                state.status_msg = "Need at least 3 vertices to finish a zone!"
                continue

            name, angle, zone_type = _prompt_zone_info(zone_counter)
            # Generate zone_id
            type_prefix = zone_type.replace("_", "-")
            count_of_type = sum(1 for z in state.zones if z.zone_type == zone_type)
            zone_id = f"{type_prefix}-{count_of_type + 1}"

            new_zone = ZoneConfig(
                zone_id=zone_id,
                name=name,
                boundary_polygon=[(float(x), float(y)) for x, y in state.current_pts],
                expected_angle_degrees=angle,
                zone_type=zone_type,
            )
            state.zones.append(new_zone)
            state.current_pts = []
            state.status_msg = f"Zone '{name}' saved ({zone_type})"
            zone_counter += 1
            print(f"[ZoneDrawer] Zone '{name}' added. Total zones: {len(state.zones)}")

        elif key == ord("n"):  # New zone, discard in-progress
            state.current_pts = []
            state.status_msg = "Started new zone"

        elif key == ord("d"):  # Delete last zone
            state.delete_last_zone()
            state.status_msg = "Last zone deleted"

        elif key == ord("s"):  # Save and quit
            ZoneLoader.save(state.zones, config_path)
            print(f"\n[ZoneDrawer] ✓ Saved {len(state.zones)} zone(s) to: {config_path}")
            for z in state.zones:
                print(f"  [{z.zone_id}] {z.name}  type={z.zone_type}  angle={z.expected_angle_degrees:.0f}°  vertices={len(z.boundary_polygon)}")
            saved = True
            break

        elif key == ord("q"):  # Quit without saving
            print("[ZoneDrawer] Quit without saving.")
            break

        elif key == 27:  # ESC
            print("[ZoneDrawer] ESC pressed, quit without saving.")
            break

    cv2.destroyAllWindows()

    if not saved:
        answer = input("\nDo you want to save before exiting? [y/N]: ").strip().lower()
        if answer == "y":
            ZoneLoader.save(state.zones, config_path)
            print(f"[ZoneDrawer] Saved {len(state.zones)} zone(s) to: {config_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive zone configuration tool for parking detection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--frame",
        required=True,
        help="Path to a sample image/frame from your footage to draw zones on",
    )
    parser.add_argument(
        "--config",
        default="config/zones.json",
        help="Output path for zones.json",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load and display existing zones from config for editing",
    )
    args = parser.parse_args()

    run_drawer(args.frame, args.config, args.load)


if __name__ == "__main__":
    main()
