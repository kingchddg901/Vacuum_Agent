"""Unit tests for mapping/map_source_runtime.py — the map_state_source runtime locators.

The HA-aware glue itself (registry/file/hass.data access) needs a live deploy, but the
extraction + version guard + presence gate + the defensive Roborock introspector are
PURE given injected plain data — tested here without Home Assistant.

[MSR-1] eufy_result_from_store: version guard, presence gate, extraction, degradation.
[MSR-2] roborock_result_from_candidates / rooms_from_mapdata / find_mapdata: MapData
        located + projected via the parser's to_img transform, no-go-immune, no-geometry,
        presence gate, structure dump — always with a diagnostics breadcrumb.
[MSR-2h/i/j] live:RB-PROJ-1: projector health counts — a dead transform is
        distinguishable from legitimately empty layers; off-grid != error.
[MSR-3] find_roomlike_collection / _walk: duck-typing, cycle-safety, attr denylist.
[MSR-4] the DREAME camera-attribute fallback (_dreame_affine / dreame_camera_candidates /
        dreame_result_from_candidates): the path map_source_coordinator takes whenever the
        MapData read is not present. Fixtures derive from robin's real transform
        (px = 682 + x*0.08, py = 845 - y*0.08, image 936x992, dock {-553,132}).
"""
import base64

import pytest

from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    eufy_live_pose_from_candidates,
    eufy_mapdata_from_candidates,
    eufy_mapdata_obj_from_candidates,
    eufy_render_data_from_store,
    eufy_result_from_mapdata,
    eufy_result_from_store,
    find_mapdata,
    find_roomlike_collection,
    mapdata_live_pose_from_candidates,
    overlays_from_mapdata,
    _mapdata_projector,
    dreame_camera_candidates,
    dreame_result_from_candidates,
    _dreame_affine,
    robot_pose_from_mapdata,
    roborock_result_from_candidates,
    rooms_from_mapdata,
    _structure_tree,
    _WALK_SKIP_ATTRS,
    _walk,
)


def _raster(w, h, blocks):
    buf = bytearray(w * h)
    for rid, x0, x1, y0, y1 in blocks:
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                buf[yy * w + xx] = (rid << 2)
    return base64.b64encode(bytes(buf)).decode()


def _store(version=1):
    """A minimal but real-shaped eufy-clean Store wrapper (version/data/map_data)."""
    return {
        "version": version,
        "minor_version": 1,
        "key": "robovac_mqtt.SERIAL",
        "data": {
            "dock_pixel": [5, 5],
            "robot_trail": [[1, 1], [8, 8]],
            "map_data": {
                "width": 10, "height": 10, "resolution": 5,
                "room_outline_width": 10, "room_outline_height": 10,
                "origin_x": 0, "origin_y": 0,
                "room_outline_origin_x": 0, "room_outline_origin_y": 0,
                "room_names": {"1": "Kitchen"},
                "room_pixels": _raster(10, 10, [(1, 0, 2, 0, 2)]),
            },
        },
    }


# --- [MSR-1] eufy_result_from_store ---------------------------------------------

def test_eufy_result_from_store_full():
    """[MSR-1] valid v1 store + present gate -> rooms + anchors."""
    out = eufy_result_from_store(_store(), expected_version=1, present=True)
    assert out["present"] is True and out["backend"] == "storage"
    assert [r["name"] for r in out["rooms"]] == ["Kitchen"]
    assert out["dock_anchor"] == [0.5, 0.4]
    assert out["robot_anchor"] == [0.8, 0.1]


def test_eufy_result_from_store_version_guard():
    """[MSR-1b] a wrapper version != expected degrades to unavailable (the #136 guard)."""
    out = eufy_result_from_store(_store(version=2), expected_version=1, present=True)
    assert out["present"] is False
    assert out["reason"] == "store_version_mismatch"


def test_eufy_result_from_store_no_version_guard_when_none():
    """[MSR-1c] expected_version=None disables the guard (any version parses)."""
    out = eufy_result_from_store(_store(version=99), expected_version=None, present=True)
    assert out["present"] is True
    assert len(out["rooms"]) == 1


def test_eufy_result_from_store_presence_gate():
    """[MSR-1d] present=False (no live-map artifact) -> absent, regardless of contents."""
    out = eufy_result_from_store(_store(), expected_version=1, present=False)
    assert out["present"] is False
    assert out["reason"] == "live_map_absent"


def test_eufy_render_data_from_store():
    """[MSR-1g] render-data reader: version guard + extract; degrade-not-crash."""
    out = eufy_render_data_from_store(_store(), expected_version=1)
    assert out["present"] is True and out["format"] == "room_pixels_v1"
    assert out["room_pixels"] == _store()["data"]["map_data"]["room_pixels"]
    assert eufy_render_data_from_store(
        _store(version=2), expected_version=1)["reason"] == "store_version_mismatch"
    assert eufy_render_data_from_store(None)["reason"] == "no_store"
    assert eufy_render_data_from_store(
        {"version": 1, "data": {}}, expected_version=1)["reason"] == "no_map_data"


def test_eufy_result_from_store_degrades():
    """[MSR-1e] non-dict / missing data / missing map_data never crash."""
    assert eufy_result_from_store(None, present=True)["reason"] == "no_store"
    assert eufy_result_from_store({"version": 1}, expected_version=1, present=True)["reason"] == "no_store_data"
    # version OK, data present, but no map_data -> no rooms -> no_segmentation
    out = eufy_result_from_store(
        {"version": 1, "data": {"dock_pixel": [1, 1]}}, expected_version=1, present=True
    )
    assert out["present"] is False
    assert out["reason"] == "no_segmentation"


# --- [MSR-2] roborock_result_from_candidates -----------------------------------

# --- Roborock fakes: a vacuum-map-parser MapData with the parser's to_img transform.
# _FakeDims mimics ImageDimensions: img_transformation = /50, no offset, Y-flip, *scale
# (scale=1). This is self-consistent so the expected normalized bbox is computable.

class _Room:
    def __init__(self, x0, y0, x1, y1, number, name=None):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.number, self.name = number, name


class _Area:
    """A no-go area / wall: HAS x0..y1 (so the OLD generic search matched it) but NO
    number — proving the MapData-targeted reader reads .rooms, not these."""
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _Pt:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def rotated(self, dims):           # identity at rotation 0 (tests use 0)
        return self


class _FakeDims:
    def __init__(self, height=100, scale=1, rotation=0):
        self.top = 0
        self.left = 0
        self.width = 100
        self.height = height
        self.scale = scale
        self.rotation = rotation

    def to_img(self, p):               # /50, Y-flip, *scale — mirrors the real transform
        return _Pt((p.x / 50) * self.scale,
                   (self.height - (p.y / 50) - 1) * self.scale)


class _FakePIL:
    def __init__(self, size):
        self.size = size


class _FakeImage:
    def __init__(self, dims, size):
        self.dimensions = dims
        self.data = _FakePIL(size)


class _MapData:
    def __init__(self, rooms, image, **extra):
        self.rooms = rooms
        self.image = image
        for k, v in extra.items():     # e.g. no_go_areas, walls
            setattr(self, k, v)


class _Coordinator:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)


def _mapdata(rooms, *, height=100, size=(100, 100), **extra):
    return _MapData(rooms, _FakeImage(_FakeDims(height=height), size), **extra)


def test_rooms_from_mapdata_transform():
    """[MSR-2] vacuum-coord Room bbox is projected via the dims.to_img transform + the
    Y-flip re-min/max'd into a normalized rendered-image bbox, with a bbox area."""
    md = _mapdata({16: _Room(500, 500, 2500, 4500, 16)})
    rooms = rooms_from_mapdata(md)
    assert len(rooms) == 1
    r = rooms[0]
    assert r["number"] == 16 and r["name"] == "Room 16"   # Roborock leaves name None
    assert r["approximate"] is True
    # to_img(500,500)=(10,89), to_img(2500,4500)=(50,9); /size(100,100); Y re-min/max'd
    assert r["bbox"] == [0.1, 0.09, 0.5, 0.89]
    # vacuum units = mm: dx=2000mm=2m, dy=4000mm=4m -> 8.0 m^2 (bbox)
    assert r["area_m2"] == 8.0
    # Real-world box dims in metres from the raw vacuum-mm corners (2000mm x 4000mm).
    assert r["width_m"] == 2.0 and r["height_m"] == 4.0


# --- Wave 3a Roborock overlay layers (overlays_from_mapdata) --------------------

class _VPoint:
    def __init__(self, x, y, a=None):
        self.x, self.y, self.a = x, y, a


class _Quad:
    """A no-go/no-mop Area: 4 corners x0,y0..x3,y3."""
    def __init__(self, corners):
        for i, (x, y) in enumerate(corners):
            setattr(self, f"x{i}", x)
            setattr(self, f"y{i}", y)


class _Seg:
    """A Wall (segment) or Zone (rect): x0,y0,x1,y1."""
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _Path:
    def __init__(self, segments):
        self.path = segments


class _ObstacleDetails:
    """vacuum-map-parser-base ObstacleDetails: type is an INT, photo_name a str."""

    def __init__(self, type_=None, photo_name=None):
        self.type, self.photo_name = type_, photo_name


class _Obstacle:
    """Real parser shape: metadata on .details — no flat .type/.photo attrs."""

    def __init__(self, x, y, type_=None, photo_name=None):
        self.x, self.y = x, y
        self.details = _ObstacleDetails(type_, photo_name)


def test_overlays_from_mapdata_full():
    """[MSR-2g] every non-room layer is projected via the same transform."""
    md = _mapdata(
        {16: _Room(500, 500, 2500, 4500, 16)},
        vacuum_position=_VPoint(1000, 2000, 90),
        charger=_VPoint(500, 500),
        vacuum_room=22,
        no_go_areas=[_Quad([(500, 500), (1500, 500), (1500, 1500), (500, 1500)])],
        no_mopping_areas=[_Quad([(500, 500), (1500, 500), (1500, 1500), (500, 1500)])],
        walls=[_Seg(500, 500, 1500, 1500)],
        zones=[_Seg(500, 500, 1500, 1500)],
        path=_Path([[_VPoint(500, 500), _VPoint(1500, 1500)]]),
        obstacles=[_Obstacle(500, 500, 0)],
    )
    ov = overlays_from_mapdata(md)
    assert ov["image_size"] == [100, 100]   # for the card's letterbox correction
    assert ov["robot_anchor"] == [0.2, 0.59] and ov["robot_heading"] == 90
    assert ov["dock_anchor"] == [0.1, 0.89]
    assert ov["current_room"] == 22
    assert ov["no_go"] == [[[0.1, 0.89], [0.3, 0.89], [0.3, 0.69], [0.1, 0.69]]]
    assert ov["no_mop"] == ov["no_go"]
    assert ov["walls"] == [[[0.1, 0.89], [0.3, 0.69]]]
    assert ov["zones"] == [[0.1, 0.69, 0.3, 0.89]]
    assert ov["path"] == [[0.1, 0.89], [0.3, 0.69]]
    assert ov["obstacles"] == [{"pos": [0.1, 0.89], "type": "cable", "has_photo": False}]


def test_overlays_from_mapdata_empty_layers_omitted():
    """[MSR-2h] absent/empty layers are omitted (not empty keys) and never crash."""
    ov = overlays_from_mapdata(_mapdata({16: _Room(0, 0, 100, 100, 16)}))
    assert "no_go" not in ov and "path" not in ov and "obstacles" not in ov
    assert "robot_anchor" not in ov   # no vacuum_position on this fake


# --- [MSR-2k] the pose extractor: ONE implementation, two readers -----------------

def _posed_mapdata():
    """A MapData carrying a robot position, dock, and current room."""
    return _mapdata(
        {16: _Room(500, 500, 2500, 4500, 16)},
        vacuum_position=_VPoint(1000, 2000, 90),
        charger=_VPoint(500, 500),
        vacuum_room=22,
    )


def test_the_card_and_the_pose_accessor_read_the_SAME_extractor():
    """[MSR-2k] THE DEFECT THIS CLOSES, stated as an equality.

    Two readers of one map disagreed about whether it had a robot on it: the card's
    overlay payload carried robot_anchor while async_get_map_live_pose reported the brand
    had no pose at all, so a stall capture drew the room and no dot. This asserts the two
    cannot drift again — not that both are 'correct', but that they are the same values
    out of the same function. Re-inline a second copy into overlays_from_mapdata and this
    goes red on the first divergence.
    """
    md = _posed_mapdata()

    ov = overlays_from_mapdata(md)
    pose = robot_pose_from_mapdata(md)

    for key in ("robot_anchor", "robot_heading", "dock_anchor", "current_room"):
        assert ov[key] == pose[key], f"{key} diverged between the two readers"
    # ...and pinned to the known-good projection, so 'identical' can't mean 'both broken'.
    assert pose["robot_anchor"] == [0.2, 0.59]


def test_the_anchor_is_normalized_never_raw_device_coords():
    """[MSR-2k] vacuum_position is in DEVICE mm; the renderer consumes 0..1.

    Passing the raw value through is the failure that puts the dot off-map entirely
    rather than in the wrong place — so it reads as a broken renderer, not a bad anchor.
    """
    pose = robot_pose_from_mapdata(_posed_mapdata())

    nx, ny = pose["robot_anchor"]
    assert 0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0
    assert [nx, ny] != [1000, 2000], "raw device coordinates reached the consumer"


def test_pose_extractor_degrades_to_empty_without_geometry():
    """[MSR-2k] No image dims → {}, not a partial pose and not a raise."""
    class _NoImage:
        rooms = {}
        image = None
        vacuum_position = _VPoint(1000, 2000, 90)

    assert robot_pose_from_mapdata(_NoImage()) == {}


def test_a_mapdata_with_no_position_is_absent_not_an_error():
    """[MSR-2k] A parked/unposed map is a real absence — present False, no anchor key."""
    md = _mapdata({16: _Room(0, 0, 100, 100, 16)})

    pose = mapdata_live_pose_from_candidates([("runtime_data", "entry1", _Coordinator(md=md))])

    assert pose["present"] is False
    assert "robot_anchor" not in pose


def test_mapdata_live_pose_walks_the_candidate_roots():
    """[MSR-2k] The generic pose reader finds the parsed map the same way the room and
    render readers do, and returns the shared live_pose_overlay shape — so a consumer
    cannot tell which brand produced it."""
    root = _Coordinator(some_holder=_Coordinator(map=_posed_mapdata()))

    pose = mapdata_live_pose_from_candidates([("runtime_data", "entry1", root)])

    assert pose["present"] is True
    assert pose["robot_anchor"] == [0.2, 0.59]
    assert pose["robot_heading"] == 90
    assert pose["dock_anchor"] == [0.1, 0.89]
    assert pose["current_room"] == 22
    assert pose["diagnostics"]["pose_at"]        # the deploy-and-discover breadcrumb


def test_mapdata_live_pose_reports_absence_with_a_breadcrumb():
    """[MSR-2k] No parsed map anywhere → the absent marker + diagnostics, never a raise."""
    pose = mapdata_live_pose_from_candidates([("hass_data", "roborock", _Coordinator(x=1))])

    assert pose["present"] is False and pose["reason"] == "no_parsed_map"
    assert pose["diagnostics"]["candidates"] == ["hass_data:roborock"]


def test_mapdata_live_pose_survives_a_hostile_provider_internal():
    """[MSR-2k] This runs on the event loop inside the snapshot; a raising property on a
    provider object must degrade that candidate to a miss, not abort the read."""
    class _Raising:
        @property
        def image(self):
            raise TypeError("provider internal raised")

        @property
        def rooms(self):
            raise TypeError("provider internal raised")

    good = _Coordinator(map=_posed_mapdata())

    pose = mapdata_live_pose_from_candidates([
        ("runtime_data", "bad", _Raising()),
        ("runtime_data", "good", good),
    ])

    assert pose["present"] is True and pose["robot_anchor"] == [0.2, 0.59]


def test_obstacle_types_normalized_from_details():
    """[MSR-2n] obstacle metadata lives on Obstacle.details (type INT, photo_name)
    — the flat o.type/o.photo reads never matched vacuum-map-parser-base and
    shipped type=None/has_photo=False for every marker. Known ints become the
    stable vocab.obstacle_type slugs; unknown ints pass through as the number
    string (locale-neutral); photo_name drives has_photo."""
    md = _mapdata(
        {16: _Room(0, 0, 100, 100, 16)},
        obstacles=[
            _Obstacle(500, 500, 1),                       # known int -> slug
            _Obstacle(500, 500, 26),                      # crossbar alias id
            _Obstacle(500, 500, 999),                     # unknown -> "999"
            _Obstacle(500, 500, None),                    # untyped marker
            _Obstacle(500, 500, 49, photo_name="p.jpg"),  # photo via details
        ],
    )
    ov = overlays_from_mapdata(md)
    assert [(o["type"], o["has_photo"]) for o in ov["obstacles"]] == [
        ("pet_waste", False),
        ("furniture_crossbar", False),
        ("999", False),
        (None, False),
        ("pet", True),
    ]


def test_obstacle_flat_type_degrade_path():
    """A parser shape carrying a flat .type and no .details still yields a
    typed marker (the degrade path, not the primary read)."""
    class _FlatObstacle:
        def __init__(self, x, y, type_):
            self.x, self.y, self.type = x, y, type_

    md = _mapdata({16: _Room(0, 0, 100, 100, 16)},
                  obstacles=[_FlatObstacle(500, 500, 2)])
    ov = overlays_from_mapdata(md)
    assert ov["obstacles"][0]["type"] == "shoes"


def test_roborock_targets_rooms_not_no_go():
    """[MSR-2b] the reader reads map_data.rooms — NOT no_go_areas (also x0..y1 rects),
    the exact bug the first live read exposed."""
    md = _mapdata(
        {16: _Room(500, 500, 2500, 4500, 16, "Dining Room")},
        no_go_areas=[_Area(23581, 22268, 23568, 23999)],
    )
    coord = _Coordinator(maps={0: md})
    out = roborock_result_from_candidates([("image_entity", "image.ivy_main_floor", coord)],
                                          present=True)
    assert out["present"] is True and out["backend"] == "memory"
    assert out["rooms"][0]["name"] == "Dining Room"        # the ROOM, not the no-go rect
    diag = out["diagnostics"]
    assert "mapdata_at" in diag and diag["room_count"] == 1
    assert diag["image_data_size"] == [100, 100]
    assert diag["rooms_raw_sample"][0]["x0"] == 500


def test_roborock_mapdata_but_no_geometry():
    """[MSR-2c] MapData found but rooms empty -> no_room_geometry + the diag (so the
    no-dock-S6 'no rooms' case is explained, not a crash)."""
    out = roborock_result_from_candidates(
        [("runtime_data", "e", _Coordinator(maps={0: _mapdata({})}))], present=True)
    assert out["present"] is False and out["reason"] == "no_room_geometry"
    assert out["diagnostics"]["room_count"] == 0


def test_roborock_no_mapdata_structure_dump():
    """[MSR-2d] nothing MapData-like -> no_parsed_map + a structure tree of the candidate."""
    out = roborock_result_from_candidates(
        [("runtime_data", "e", _Coordinator(stuff={"x": 1}))], present=True)
    assert out["present"] is False and out["reason"] == "no_parsed_map"
    assert out["diagnostics"]["candidates"] == ["runtime_data:e"]
    assert "structure" in out["diagnostics"]


def test_roborock_presence_gate():
    """[MSR-2e] present=False short-circuits before any walk, still reports candidates."""
    out = roborock_result_from_candidates(
        [("hass_data", "roborock", _Coordinator())], present=False)
    assert out["present"] is False and out["reason"] == "live_map_absent"
    assert out["diagnostics"]["candidates"] == ["hass_data:roborock"]


def test_eufy_live_pose_from_candidates():
    """[MSR-2i] find the fork's live robot/dock pixel + trail on the in-memory coordinator
    (matched by attr PRESENCE); structure dump when absent."""
    root = _Coordinator(_home_trait=_Coordinator(
        _robot_pixel=[10, 20], _dock_pixel=[5, 6],
        _robot_trail=[(1, 1), (2, 2)], _robot_angle=45))
    out = eufy_live_pose_from_candidates(
        [("hass_data", "robovac_mqtt", root)],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"],
        heading_attrs=["_robot_angle"], trail_attrs=["_robot_trail"])
    assert out["present"] is True
    assert out["robot_pixel"] == [10, 20] and out["dock_pixel"] == [5, 6]
    assert out["robot_heading"] == 45
    assert out["trail_pixels"] == [(1, 1), (2, 2)]
    assert out["diagnostics"]["robot_docked"] is False
    assert "pose_at" in out["diagnostics"]
    # nothing with the robot+dock attrs -> absent + structure dump
    out2 = eufy_live_pose_from_candidates(
        [("hass_data", "robovac_mqtt", _Coordinator(foo=1))],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"], heading_attrs=[])
    assert out2["present"] is False and "structure" in out2["diagnostics"]


def test_eufy_live_pose_docked_robot_pixel_none():
    """[MSR-2j] the holder is matched on the attr EXISTING even though _robot_pixel is None
    while docked (the fork nulls it) -> present via the dock; flags robot_docked."""
    root = _Coordinator(coordinators=[_Coordinator(
        _robot_pixel=None, _dock_pixel=(8, 8), _robot_trail=[(3, 3)])])
    out = eufy_live_pose_from_candidates(
        [("hass_data", "robovac_mqtt", root)],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"],
        trail_attrs=["_robot_trail"])
    assert out["present"] is True
    assert out["robot_pixel"] is None and out["dock_pixel"] == [8, 8]
    assert out["diagnostics"]["robot_docked"] is True
    # a robot attr WITHOUT a dock attr is not a pose holder (needs both) -> miss
    miss = eufy_live_pose_from_candidates(
        [("hass_data", "robovac_mqtt", _Coordinator(_robot_pixel=[1, 2]))],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"])
    assert miss["present"] is False and "structure" in miss["diagnostics"]


def test_eufy_mapdata_from_candidates():
    """[MSR-2l] find the fork's in-memory MapData on the coordinator and convert it to the
    .storage map_data DICT shape (so the existing decoders consume it unchanged)."""
    md_obj = _Coordinator(
        room_pixels=bytes([20]) * 100,  # 10x10 raster, every byte rid=20>>2=5
        width=10, height=10, resolution=5, origin_x=0, origin_y=0,
        room_outline_width=10, room_outline_height=10,
        room_outline_origin_x=0, room_outline_origin_y=0, room_names={"5": "K"},
    )
    root = _Coordinator(coordinators=[_Coordinator(_map_data=md_obj)])
    out = eufy_mapdata_from_candidates(
        [("hass_data", "robovac_mqtt", root)], mapdata_attrs=["_map_data"])
    assert out["present"] is True
    assert out["map_data"]["width"] == 10 and out["map_data"]["room_outline_width"] == 10
    assert isinstance(out["map_data"]["room_pixels"], str)   # base64, decoder-ready
    assert isinstance(out["version"], str) and len(out["version"]) == 12
    assert "mapdata_at" in out["diagnostics"]
    # no MapData on any walked node -> absent (caller falls back to .storage)
    miss = eufy_mapdata_from_candidates(
        [("hass_data", "robovac_mqtt", _Coordinator(foo=1))], mapdata_attrs=["_map_data"])
    assert miss["present"] is False and miss["reason"] == "no_mapdata"


def test_eufy_mapdata_obj_from_candidates():
    """[MSR-2n] cheap locate: the RAW MapData object + a version from the RAW raster bytes
    (no base64 convert), so the hot path can cache-check the version before converting."""
    rp = bytes([20]) * 100
    md_obj = _Coordinator(room_pixels=rp, width=10, height=10)
    root = _Coordinator(coordinators=[_Coordinator(_map_data=md_obj)])
    out = eufy_mapdata_obj_from_candidates(
        [("hass_data", "robovac_mqtt", root)], mapdata_attrs=["_map_data"])
    assert out["present"] is True
    assert out["obj"] is md_obj                              # the raw object, NOT converted
    assert isinstance(out["version"], str) and len(out["version"]) == 12
    assert "mapdata_at" in out["diagnostics"]
    # same raster -> same version (cache hit); a re-map (different raster) -> different version
    same = eufy_mapdata_obj_from_candidates(
        [("hass_data", "robovac_mqtt",
          _Coordinator(coordinators=[_Coordinator(_map_data=_Coordinator(room_pixels=bytes([20]) * 100))]))],
        mapdata_attrs=["_map_data"])
    assert same["version"] == out["version"]
    diff = eufy_mapdata_obj_from_candidates(
        [("hass_data", "robovac_mqtt",
          _Coordinator(coordinators=[_Coordinator(_map_data=_Coordinator(room_pixels=bytes([24]) * 100))]))],
        mapdata_attrs=["_map_data"])
    assert diff["version"] != out["version"]
    # no MapData -> absent
    miss = eufy_mapdata_obj_from_candidates(
        [("hass_data", "robovac_mqtt", _Coordinator(foo=1))], mapdata_attrs=["_map_data"])
    assert miss["present"] is False and miss["reason"] == "no_mapdata"


def test_eufy_mapdata_obj_from_candidates_device_id_selects():
    """[MSR-2o] RP-026/LC-1/EXT-1: with two coordinators, device_id picks the
    matching one instead of the first-hit; an unknown device_id is absent with
    device_not_found rather than falling back to somebody else's map."""
    coord_a = _Coordinator(device_id="AAA", _map_data=_Coordinator(room_pixels=bytes([1]) * 8))
    coord_b = _Coordinator(device_id="BBB", _map_data=_Coordinator(room_pixels=bytes([2]) * 8))
    candidates = [
        ("hass_data", "robovac_mqtt[0]", coord_a),
        ("hass_data", "robovac_mqtt[1]", coord_b),
    ]

    served_b = eufy_mapdata_obj_from_candidates(
        candidates, mapdata_attrs=["_map_data"], device_id="BBB")
    assert served_b["present"] is True
    assert served_b["obj"] is coord_b._map_data

    unknown = eufy_mapdata_obj_from_candidates(
        candidates, mapdata_attrs=["_map_data"], device_id="ZZZ")
    assert unknown["present"] is False
    assert unknown["reason"] == "device_not_found"

    # no device_id -> unchanged first-hit fallback (single-coordinator/legacy path).
    first_hit = eufy_mapdata_obj_from_candidates(candidates, mapdata_attrs=["_map_data"])
    assert first_hit["obj"] is coord_a._map_data


def test_eufy_mapdata_obj_from_candidates_version_covers_geometry():
    """[MSR-2p] RP-026/EXT-2: identical raster bytes at a DIFFERENT origin/resolution
    must version-miss — geometry decides where the pixels sit and is not optional."""
    same_raster = bytes([9]) * 8
    before = eufy_mapdata_obj_from_candidates(
        [("hass_data", "k", _Coordinator(
            _map_data=_Coordinator(room_pixels=same_raster, origin_x=0, origin_y=0, res=50)))],
        mapdata_attrs=["_map_data"],
    )
    after = eufy_mapdata_obj_from_candidates(
        [("hass_data", "k", _Coordinator(
            _map_data=_Coordinator(room_pixels=same_raster, origin_x=1500, origin_y=0, res=40)))],
        mapdata_attrs=["_map_data"],
    )
    assert before["version"] != after["version"]


def test_eufy_result_from_mapdata():
    """[MSR-2m] the memory-backend result builder: static rooms + image_size from the converted
    in-memory map_data dict (no stale .storage anchors — those come from the live pose)."""
    md = _store()["data"]["map_data"]
    res = eufy_result_from_mapdata(md, present=True)
    assert res["present"] is True and res["backend"] == "memory"
    assert res["rooms"][0]["number"] == 1
    assert res["image_size"] == [10, 10]
    assert "robot_anchor" not in res and "current_room" not in res  # pose layered separately
    # presence gate + a missing raster both degrade to absent (caller falls back to .storage)
    assert eufy_result_from_mapdata(md, present=False)["present"] is False
    assert eufy_result_from_mapdata({}, present=True)["present"] is False
    assert eufy_result_from_mapdata(None, present=True)["present"] is False


def test_eufy_live_pose_never_raises_on_raising_property():
    """[MSR-2k] a provider object exposing a configured name as a property whose getter RAISES
    (a non-AttributeError, e.g. mid fork-schema-merge) must degrade to a miss, not propagate —
    this runs on the event loop inside the snapshot service and must never crash it."""
    class _Hostile:
        @property
        def _robot_pixel(self):  # noqa: D401 - a getter that blows up on access
            raise RuntimeError("provider internals shifted")

        @property
        def _dock_pixel(self):
            raise KeyError("nope")

    # the hostile object is reachable in the walk; nothing should escape
    root = _Coordinator(coordinators=[_Hostile()])
    out = eufy_live_pose_from_candidates(
        [("hass_data", "robovac_mqtt", root)],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"])
    assert out["present"] is False   # degraded cleanly, no exception


def test_find_mapdata_nested():
    """[MSR-2f] find_mapdata locates the MapData under attr+dict layers (image entity ->
    _home_trait._map_content.map_data shape)."""
    root = _Coordinator(_home_trait=_Coordinator(
        _map_content=_Coordinator(map_data=_mapdata({1: _Room(0, 0, 1, 1, 1)}))))
    md, path = find_mapdata(root)
    assert md is not None and "map_data" in path


# --- [MSR-3] find_roomlike_collection / _walk (generic utilities) ----------------

def test_find_roomlike_nested():
    """[MSR-3] finds a Room dict buried under attribute + dict layers."""
    coll, path = find_roomlike_collection(
        _Coordinator(maps={"main": _Coordinator(rooms={1: _Room(0, 0, 1, 1, 1)})})
    )
    assert coll is not None and "rooms" in path


def test_find_roomlike_cycle_safe():
    """[MSR-3b] a self-referential graph terminates (visited-set) and still finds rooms."""
    c = _Coordinator(maps={0: _Coordinator(rooms={1: _Room(0, 0, 1, 1, 1)})})
    c.self_ref = c            # cycle
    coll, _ = find_roomlike_collection(c)
    assert coll is not None


def test_walk_skips_denylisted_attrs():
    """[MSR-3c] _walk does not descend through giant/cyclic attrs (e.g. 'hass'),
    so rooms reachable ONLY via a denylisted attr are not returned — and it never
    blows up walking one."""
    class _Box:
        pass
    b = _Box()
    b.hass = _Coordinator(maps={0: _Coordinator(rooms={1: _Room(0, 0, 1, 1, 1)})})
    coll, _ = find_roomlike_collection(b)
    assert coll is None


def test_walk_node_cap_terminates():
    """[MSR-3d] a wide structure is bounded by max_nodes (no runaway)."""
    big = {str(i): {"a": i} for i in range(10000)}
    hit, _ = _walk(big, lambda o: False, max_nodes=50)
    assert hit is None


def test_walk_descends_into_slots_object():
    """[MSR-3e] RB-7: a __slots__ object has no __dict__ — the walk must fall back to
    its declared slot names instead of dead-ending as an opaque leaf."""
    class _SlottedRoom:
        __slots__ = ("x0", "y0", "x1", "y1")

        def __init__(self):
            self.x0, self.y0, self.x1, self.y1 = 0, 0, 1, 1

    class _SlottedHolder:
        __slots__ = ("rooms",)

        def __init__(self, rooms):
            self.rooms = rooms

    root = _SlottedHolder({"1": _SlottedRoom()})
    hit, path = _walk(root, lambda o: isinstance(o, _SlottedRoom))
    assert hit is not None and isinstance(hit, _SlottedRoom)
    assert "rooms" in path


def test_walk_slots_denylist_still_applies():
    """[MSR-3f] the __slots__ fallback still honors the attribute denylist (same as the
    __dict__ path, test_walk_skips_denylisted_attrs above) — a Room-like collection
    reachable ONLY through a denylisted slot (e.g. 'hass') must not be found."""
    class _SlottedBox:
        __slots__ = ("hass",)

        def __init__(self, hass):
            self.hass = hass

    box = _SlottedBox(_Coordinator(maps={0: _Coordinator(rooms={1: _Room(0, 0, 1, 1, 1)})}))
    coll, _ = find_roomlike_collection(box)
    assert coll is None


# --- defensive-introspector hardening (blind-agent flagged; this module's JOB
# --- is surviving unknown/malformed runtime shapes, so these are behavior, not padding) ---

def test_eufy_render_data_from_store_bad_shapes():
    """[MSR-1b] eufy_render_data_from_store degrades (never raises) on EVERY bad shape."""
    f = eufy_render_data_from_store
    assert f("not a dict")["reason"] == "no_store"
    assert f({"version": 2, "data": {}}, expected_version=1)["reason"] == "store_version_mismatch"
    assert f({"data": "nope"})["reason"] == "no_store_data"            # data not a dict
    assert f({"data": {"map_data": "nope"}})["reason"] == "no_map_data"
    assert f({"data": {"map_data": {}}})["reason"] == "no_segmentation"  # decoder -> None


# Minimal fakes mimicking the vacuum-map-parser MapData/Room/Image the introspector duck-types.
class _FPoint:
    def __init__(self, x, y): self.x, self.y = x, y
    def rotated(self, dims): return self


class _FDims:
    rotation = 0
    def __init__(self, raise_on=None): self._raise_on = raise_on
    def to_img(self, p):
        if self._raise_on is not None and p.x == self._raise_on:
            raise ValueError("bad point")
        return _FPoint(p.x, p.y)


class _FData:
    def __init__(self, size=(100, 100)): self.size = size


class _FImage:
    def __init__(self, dims=None, data=None):
        self.dimensions = _FDims() if dims is None else dims
        self.data = _FData() if data is None else data


class _FRoom:
    def __init__(self, x0, y0, x1, y1, number=1, name=None):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.number, self.name = number, name


class _FMap:
    def __init__(self, rooms, image="default"):
        self.rooms = rooms
        self.image = _FImage() if image == "default" else image


def test_rooms_from_mapdata_malformed_and_skips():
    """[MSR-2b] rooms_from_mapdata: [] on missing rooms / no projector geometry; skips a
    None-corner room and a projection-failing room; keeps the valid one. Never raises."""
    assert rooms_from_mapdata(_FMap(rooms=None)) == []                       # rooms None
    assert rooms_from_mapdata(_FMap(rooms={1: _FRoom(0, 0, 50, 50)}, image=None)) == []  # no projector

    md = _FMap(rooms={
        1: _FRoom(10, 10, 60, 60),      # valid -> kept
        2: _FRoom(None, 0, 50, 50),     # None corner -> skipped
        3: _FRoom(999, 0, 50, 50),      # projection raises -> skipped
    }, image=_FImage(dims=_FDims(raise_on=999)))
    out = rooms_from_mapdata(md)
    assert len(out) == 1 and out[0]["number"] == 1 and out[0]["approximate"] is True


def test_rooms_from_mapdata_bad_projector_geometry():
    """[MSR-2c] the projector returns None (=> rooms []) on zero / unparseable image dims."""
    assert rooms_from_mapdata(_FMap(rooms={1: _FRoom(0, 0, 1, 1)},
                                    image=_FImage(data=_FData(size=(0, 0))))) == []
    assert rooms_from_mapdata(_FMap(rooms={1: _FRoom(0, 0, 1, 1)},
                                    image=_FImage(data=_FData(size="bad")))) == []


def test_has_named_attr_raising_descriptor():
    """[MSR-3b] a class-level property that RAISES must not escape the BFS -> not-present; a
    normal class attr (not in instance __dict__) is still found via the hasattr fallback."""
    from custom_components.eufy_vacuum.mapping.map_source_runtime import _has_named_attr

    class _Raises:
        @property
        def boom(self): raise KeyError("descriptor blew up")

    class _HasClassAttr:
        foo = 1

    assert _has_named_attr(_Raises(), ["boom"]) is False
    assert _has_named_attr(_HasClassAttr(), ["foo"]) is True


def test_eufy_live_pose_hostile_candidate_then_success():
    """[MSR-3c] a candidate whose provider internal RAISES degrades to a miss (not an abort);
    a later clean candidate still resolves the pose."""
    class _RaisingHeading:
        _robot_pixel = [1, 2]
        _dock_pixel = [3, 4]
        @property
        def _heading(self): raise TypeError("provider internal raised")

    class _Good:
        def __init__(self):
            self._robot_pixel = [5, 6]
            self._dock_pixel = [7, 8]

    out = eufy_live_pose_from_candidates(
        [("bad", "1", _RaisingHeading()), ("good", "2", _Good())],
        robot_attrs=["_robot_pixel"], dock_attrs=["_dock_pixel"], heading_attrs=["_heading"],
    )
    assert out["present"] is True
    assert out["robot_pixel"] == [5, 6] and out["dock_pixel"] == [7, 8]


# --- live:RB-PROJ-1 — a dead projector must not look like empty layers ----------
#
# `proj` swallows Exception per point and every caller drops silently, and
# overlays_from_mapdata omits empty layers by contract. So a change inside
# vacuum-map-parser-roborock's ImageDimensions.to_img — a dependency HA core bumps
# on its own schedule — empties rooms, no-go, no-mop, walls, zones, path and
# obstacles in one stroke while the map still renders. Nothing counted, nothing
# logged: `_LOGGER` was declared and never used.

class _BrokenDims:
    """ImageDimensions whose to_img raises — i.e. the library changed underneath us."""
    rotation = 0

    def to_img(self, _point):
        raise AttributeError("to_img signature changed")


def test_projector_counts_are_emitted_even_when_healthy():
    """[MSR-2h] the counts ride ALONG, including all-zero, so a consumer can tell
    'empty because nothing was there' from 'empty because everything failed'."""
    md = _mapdata(
        {16: _Room(500, 500, 2500, 4500, 16)},
        walls=[_Seg(500, 500, 1500, 1500)],
    )
    ov = overlays_from_mapdata(md)
    assert "projector" in ov, "the health counts must always be present"
    p = ov["projector"]
    assert p["calls"] > 0
    assert p["errors"] == 0
    assert ov.get("walls"), "precondition: the healthy layer really did render"


def test_a_dead_projector_is_distinguishable_from_empty_layers():
    """[MSR-2i] THE DEFECT. With to_img raising, every layer drops out — and the
    counts say WHY, which is the whole difference this finding was about."""
    md = _mapdata(
        {16: _Room(500, 500, 2500, 4500, 16)},
        vacuum_position=_VPoint(1000, 2000, 90),
        charger=_VPoint(500, 500),
        no_go_areas=[_Quad([(500, 500), (1500, 500), (1500, 1500), (500, 1500)])],
        walls=[_Seg(500, 500, 1500, 1500)],
        zones=[_Seg(500, 500, 1500, 1500)],
        obstacles=[_Obstacle(500, 500, 0)],
    )
    md.image.dimensions = _BrokenDims()

    ov = overlays_from_mapdata(md)

    # every drawable layer is gone — exactly the silent failure, reproduced
    for layer in ("robot_anchor", "dock_anchor", "no_go", "walls", "zones", "obstacles"):
        assert layer not in ov, f"{layer} unexpectedly survived a dead projector"

    # ...but it is no longer SILENT: the counts distinguish it from empty input
    p = ov["projector"]
    assert p["calls"] > 0
    assert p["errors"] == p["calls"], "a total failure must read as total"
    assert p["out_of_grid"] == 0, "a transform error is not an out-of-bounds rejection"


def test_out_of_grid_rejections_are_not_counted_as_errors():
    """[MSR-2j] The two None returns mean opposite things. reject_out_of_grid is a
    HEALTHY discard; counting it as an error would make the alarm cry wolf and
    train everyone to ignore the one line that matters."""
    md = _mapdata({16: _Room(500, 500, 2500, 4500, 16)})
    proj = _mapdata_projector(md)[0]

    assert proj(500, 500) is not None                       # in-frame
    assert proj(10_000_000, 10_000_000, reject_out_of_grid=True) is None

    assert proj.errors == 0, "an off-grid point is not a broken transform"
    assert proj.out_of_grid == 1
    assert proj.calls == 2


# ---------------------------------------------------------------------------
# [MSR-4] The Dreame camera-attribute fallback.
#
# map_source_coordinator.py calls dreame_camera_candidates + dreame_result_from_candidates
# whenever the MapData read does not yield a present result -- live code on every Dreame
# install whose decoded map is unavailable. It had ZERO tests: 82 statements, none of them
# ever executed, across three functions.
#
# THE NUMBERS BELOW ARE REAL, from robin (Chris's own Dreame, field report 2026-08-09):
# the derived transform for that house is `px = 682 + x*0.08`, `py = 845 - y*0.08`, the
# rendered image is 936x992, and the dock sat at vacuum {-553, 132}. Deriving the fixture
# from the real producer is the point -- an invented affine would encode my assumption
# about the frame rather than the device's.
# ---------------------------------------------------------------------------

# robin's transform, used to MANUFACTURE the calibration pairs the device would publish.
def _px(x: float) -> float:
    return 682.0 + x * 0.08


def _py(y: float) -> float:
    return 845.0 - y * 0.08


def _cal(*vacuum_points):
    """3 vacuum->pixel pairs in the shape the camera attribute carries."""
    return [
        {"vacuum": {"x": vx, "y": vy}, "map": {"x": _px(vx), "y": _py(vy)}}
        for vx, vy in vacuum_points
    ]


_CAL_ROBIN = _cal((0, 0), (1000, 0), (0, 1000))   # non-collinear, det = 1e6


class _FakeState:
    def __init__(self, attributes):
        self.attributes = attributes


class _FakeHass:
    """Only `states.get` is reached by dreame_camera_candidates."""

    def __init__(self, states=None):
        self._states = states or {}

    @property
    def states(self):
        return self

    def get(self, eid):
        return self._states.get(eid)


# A room as the device actually publishes it: the bbox fields the code reads, PLUS the
# dozen it does not (LIVE-CAPABILITY-AUDIT lists cleaning_mode, floor_material, type...).
# Carrying the extras is deliberate -- it proves the reader ignores them rather than
# happening to work on a fixture trimmed to what it needs.
_ROOM_REAL = {
    "x0": -1000, "y0": -500, "x1": 1000, "y1": 1500,
    "room_id": 3, "name": "Kitchen", "custom_name": "Kitchen",
    "cleaning_mode": 2, "cleaning_route": 1, "cleaning_times": 1, "color_index": 0,
    "floor_material": 1, "floor_material_direction": 0, "icon": "", "index": 0,
    "order": 1, "suction_level": 2, "type": 3, "visibility": True,
    "water_volume": 2, "wetness_level": 16, "x": 0, "y": 500,
}


def test_msr4a_dreame_affine_recovers_the_real_device_transform():
    """[MSR-4a] three pairs define the affine, and it must reproduce robin's transform.

    Cramer's rule is the kind of code that looks right and is off by a term. The bite is
    a FOURTH point, not one of the three fitted: the dock, at the position the field
    report verified by two unrelated routes.

    ABLATION: swap any coefficient in `_coeffs` and this goes red at the dock.
    """
    proj = _dreame_affine(_CAL_ROBIN)
    assert proj is not None
    # The three fitted points come back exactly...
    for vx, vy in ((0, 0), (1000, 0), (0, 1000)):
        px, py = proj(vx, vy)
        assert px == pytest.approx(_px(vx)) and py == pytest.approx(_py(vy))
    # ...and so does a point the fit never saw: robin's dock at {-553, 132}.
    px, py = proj(-553, 132)
    assert px == pytest.approx(637.76) and py == pytest.approx(834.44)


def test_msr4b_dreame_affine_refuses_fewer_than_three_pairs():
    """[MSR-4b] two pairs cannot define an affine. ABLATION: drop the len() guard and
    this raises IndexError instead of returning None, so the caller sees a crash rather
    than `no_calibration`."""
    assert _dreame_affine(_CAL_ROBIN[:2]) is None
    assert _dreame_affine([]) is None
    assert _dreame_affine(None) is None


def test_msr4c_dreame_affine_refuses_collinear_points():
    """[MSR-4c] three points on a line are a singular system — the determinant vanishes
    and the 'solution' would be arbitrary.

    ABLATION: remove the `abs(det) < 1e-9` guard and this raises ZeroDivisionError.
    Shipping that means a degenerate calibration frame crashes a map refresh instead of
    degrading to `no_calibration`.
    """
    assert _dreame_affine(_cal((0, 0), (1000, 1000), (2000, 2000))) is None


def test_msr4d_dreame_affine_refuses_malformed_pairs():
    """[MSR-4d] the attribute comes off a device; it is not trusted to be well-formed.
    Four shapes, each hitting a different exception in the same guard."""
    assert _dreame_affine([{"vacuum": {"x": 0, "y": 0}}] * 3) is None          # KeyError
    assert _dreame_affine([{"vacuum": {"x": "a", "y": 0}, "map": {"x": 1, "y": 1}}] * 3) is None
    assert _dreame_affine([None, None, None]) is None                          # TypeError
    assert _dreame_affine("not a list") is None


def test_msr4e_camera_candidates_without_an_image_entity():
    """[MSR-4e] no declared image entity -> a named reason, not an exception."""
    out = dreame_camera_candidates(_FakeHass(), {}, image_entity_id=None)
    assert out["present"] is False and out["reason"] == "no_image_entity"
    assert out["diagnostics"]["image_entity_id"] is None


def test_msr4f_camera_candidates_when_the_entity_has_no_state():
    """[MSR-4f] the entity is declared but absent from the state machine (not yet set up,
    or removed). ABLATION: drop the `attrs is None` branch and this raises AttributeError
    inside a map refresh."""
    out = dreame_camera_candidates(_FakeHass(), {}, image_entity_id="camera.robin_map")
    assert out["present"] is False and out["reason"] == "live_map_absent"
    assert out["diagnostics"]["read"] == "image_entity_absent"


def test_msr4g_camera_candidates_reads_the_live_map_when_it_carries_rooms():
    """[MSR-4g] the straightforward path, and the diagnostics breadcrumb that names it."""
    hass = _FakeHass({"camera.robin_map": _FakeState({
        "rooms": {"3": _ROOM_REAL},
        "calibration_points": _CAL_ROBIN,
        "vacuum_position": {"x": 100, "y": 200, "a": 90},
        "charger_position": {"x": -553, "y": 132, "a": 0},
    })})
    out = dreame_camera_candidates(hass, {"map_pixel_size": [936, 992]},
                                   image_entity_id="camera.robin_map")
    assert out["present"] is True
    assert out["diagnostics"]["read"] == "live_map_rooms"
    assert out["rooms_raw"] == {"3": _ROOM_REAL}
    assert out["pixel_size"] == [936, 992]


def test_msr4h_camera_candidates_falls_back_to_the_saved_map_for_geometry():
    """[MSR-4h] THE REASON THIS FALLBACK EXISTS, and the subtle half of it.

    `as_dict()` carries room GEOMETRY only for a saved/restored map; the live current-map
    camera omits `rooms`. So geometry comes from `<entity>_1` -- but the ROBOT POSITION
    must still come from the LIVE entity, because the saved map's copy is wherever the
    robot was when that map was stored. The merge is deliberately one key wide.

    ABLATION: drop the `vacuum_position` filter from the merge (take `saved` wholesale)
    and this goes red with the stale position — the robot puck would be drawn at a
    position from another session.
    """
    hass = _FakeHass({
        "camera.robin_map": _FakeState({
            "rooms": None,                                   # live map: no geometry
            "calibration_points": _CAL_ROBIN,
            "vacuum_position": {"x": 100, "y": 200, "a": 90},    # LIVE, current
            "charger_position": {"x": -553, "y": 132, "a": 0},
        }),
        "camera.robin_map_1": _FakeState({
            "rooms": {"3": _ROOM_REAL},                      # saved map: geometry
            "calibration_points": _CAL_ROBIN,
            "vacuum_position": {"x": -9999, "y": -9999, "a": 0},  # STALE, from storage
            "charger_position": {"x": -553, "y": 132, "a": 0},
        }),
    })
    out = dreame_camera_candidates(hass, {}, image_entity_id="camera.robin_map")
    assert out["present"] is True
    assert out["diagnostics"]["read"] == "saved_map_rooms"
    assert out["rooms_raw"] == {"3": _ROOM_REAL}
    assert out["robot"] == {"x": 100, "y": 200, "a": 90}, (
        "the robot position must come from the LIVE camera, never the saved map's copy"
    )


def test_msr4i_result_absent_when_the_gate_is_closed():
    """[MSR-4i] the presence gate wins over anything the candidates carry, and the
    diagnostics breadcrumb survives into the absent marker so the log still says where
    the read landed."""
    cand = {"present": True, "reason": "whatever", "diagnostics": {"read": "live_map_rooms"}}
    out = dreame_result_from_candidates(cand, present=False)
    assert out["present"] is False
    assert out["diagnostics"] == {"read": "live_map_rooms"}


def test_msr4j_result_without_calibration_says_so():
    """[MSR-4j] a map with geometry but no usable calibration cannot be projected, and the
    reason has to distinguish that from an absent map — they need different fixes."""
    out = dreame_result_from_candidates(
        {"present": True, "rooms_raw": {"3": _ROOM_REAL}, "calibration": None,
         "diagnostics": {}},
        present=True,
    )
    assert out["present"] is False and out["reason"] == "no_calibration"


def test_msr4k_result_projects_a_real_room_end_to_end():
    """[MSR-4k] ONE REAL ARTIFACT, end to end — the test the per-field ones cannot replace.

    Real calibration, a real room record with all its extra fields, real dock and robot
    positions. Every number below is derived from robin's transform by hand, so a change
    to the projection, the normalisation, the bbox sort or the metre conversion moves one
    of them.

    `map_pixel_size` is declared here. PRODUCTION DOES NOT DECLARE IT (the Dreame adapter
    sets it None on purpose — "the MapData path uses dimensions.grid_size"), so the
    normalised branch is the one a future tuning pass would switch on. [MSR-4m] covers the
    path production actually takes.
    """
    cand = {
        "present": True,
        "calibration": _CAL_ROBIN,
        "rooms_raw": {"3": _ROOM_REAL},
        "robot": {"x": 100, "y": 200, "a": 90},
        "dock": {"x": -553, "y": 132, "a": 0},
        "pixel_size": [936, 992],
        "diagnostics": {"read": "live_map_rooms"},
    }
    out = dreame_result_from_candidates(cand, present=True)

    assert out["present"] is True and out["backend"] == "camera_attrs"
    (room,) = out["rooms"]
    assert room["number"] == 3 and room["name"] == "Kitchen"
    assert room["approximate"] is True
    # 2000 vacuum units across and 2000 up -> 2.0 m each way.
    assert room["width_m"] == 2.0 and room["height_m"] == 2.0
    # corners (602,885) and (762,725) in pixels, normalised by 936x992 and sorted.
    assert room["bbox"] == pytest.approx(
        [602 / 936, 725 / 992, 762 / 936, 885 / 992], abs=1e-9
    )
    assert out["robot_anchor"] == pytest.approx([690 / 936, 829 / 992], abs=1e-9)
    assert out["dock_anchor"] == pytest.approx([637.76 / 936, 834.44 / 992], abs=1e-9)
    assert out["calibration_points"] == _CAL_ROBIN
    assert out["diagnostics"] == {"read": "live_map_rooms"}


def test_msr4l_a_docked_robot_publishes_no_robot_anchor():
    """[MSR-4l] `a == 32767` is Dreame's docked/unknown sentinel. Projecting it would put
    the puck at a real-looking position derived from a non-position.

    ABLATION: remove the sentinel check and this goes red with a robot_anchor present.
    The dock anchor must still be emitted — the robot being docked says nothing about
    where the dock is.
    """
    cand = {
        "present": True, "calibration": _CAL_ROBIN, "rooms_raw": {"3": _ROOM_REAL},
        "robot": {"x": 100, "y": 200, "a": 32767},
        "dock": {"x": -553, "y": 132, "a": 0},
        "pixel_size": [936, 992], "diagnostics": {},
    }
    out = dreame_result_from_candidates(cand, present=True)
    assert "robot_anchor" not in out
    assert "dock_anchor" in out


def test_msr4m_without_a_declared_pixel_size_the_frame_stays_in_pixels():
    """[MSR-4m] THE PATH PRODUCTION TAKES. The Dreame adapter declares
    `map_pixel_size: None`, so `_norm` returns raw pixel coordinates rather than 0..1.

    That is deliberate and documented at the declaration, not an oversight — but it means
    consumers of this fallback see a different coordinate frame than the MapData path, and
    nothing else states it. Pinning it here so a future change to the default is a
    decision with a red test rather than a silent reframing.
    """
    cand = {
        "present": True, "calibration": _CAL_ROBIN, "rooms_raw": {"3": _ROOM_REAL},
        "robot": None, "dock": {"x": -553, "y": 132, "a": 0},
        "pixel_size": None, "diagnostics": {},
    }
    out = dreame_result_from_candidates(cand, present=True)
    (room,) = out["rooms"]
    assert room["bbox"] == pytest.approx([602.0, 725.0, 762.0, 885.0], abs=1e-9), (
        "unnormalised pixel frame, not 0..1 — see the adapter's map_pixel_size comment"
    )
    assert out["dock_anchor"] == pytest.approx([637.76, 834.44], abs=1e-9)


def test_msr4n_malformed_rooms_are_skipped_not_fatal():
    """[MSR-4n] four shapes the device can publish, none of which may take down a refresh.

    A room missing one bbox edge, a non-dict entry, and a LIST of rooms rather than a dict
    (the `enumerate` branch — which also supplies the room number when `room_id` is
    absent). The good room still comes through, which is the real assertion: one bad
    record must not cost the others.

    MEASURED, because the obvious claim was wrong. Removing the
    `if None in (x0, y0, x1, y1): continue` guard does NOT redden this test: that guard is
    REDUNDANT. A None edge reaches `_norm`, `float(None)` raises TypeError, the except
    returns None, and `if not c0 or not c1: continue` drops the room anyway. So this
    asserts the OUTCOME -- a malformed room is skipped and the others survive -- while the
    guard that actually delivers it is `_norm`'s except, pinned by [MSR-4p]. Do not read
    the bbox-edge check as load-bearing; an ablation says it is belt-and-braces.
    """
    cand = {
        "present": True, "calibration": _CAL_ROBIN, "pixel_size": None,
        "robot": None, "dock": None, "diagnostics": {},
        "rooms_raw": {
            "1": {"x0": 0, "y0": 0, "x1": None, "y1": 10},   # missing an edge
            "2": "not a dict",
            "3": _ROOM_REAL,
        },
    }
    out = dreame_result_from_candidates(cand, present=True)
    assert [r["number"] for r in out["rooms"]] == [3]

    # The list form: no room_id, so the index supplies the number and the name.
    listed = dict(cand, rooms_raw=[{"x0": -1000, "y0": -500, "x1": 1000, "y1": 1500}])
    out2 = dreame_result_from_candidates(listed, present=True)
    (room,) = out2["rooms"]
    assert room["number"] == 0 and room["name"] == "Room 0"


def test_msr4o_geometry_present_but_no_projectable_rooms_is_absent():
    """[MSR-4o] `build_map_source_result` treats an empty room list as NOT present, even
    with present=True — a map whose every room failed to project is not a usable map, and
    a consumer must hide rather than render an empty floor plan.

    ABLATION: this is the contract of the shared builder; it goes red if the fallback
    starts returning present=True with rooms=[].
    """
    cand = {
        "present": True, "calibration": _CAL_ROBIN, "pixel_size": None,
        "robot": None, "dock": None, "diagnostics": {"read": "live_map_rooms"},
        "rooms_raw": {"1": {"x0": None, "y0": None, "x1": None, "y1": None}},
    }
    out = dreame_result_from_candidates(cand, present=True)
    assert out["present"] is False
    assert out["reason"] == "no_segmentation"


def test_msr4p_non_numeric_coordinates_are_skipped_everywhere():
    """[MSR-4p] the device publishes strings sometimes; none of them may crash a refresh.

    One input exercises three guards at once, because they share `_norm`: a room corner
    that will not float (the `except (TypeError, ValueError)` inside `_norm`), the
    `continue` that drops a room whose corner did not project, and both `if p:` edges
    that suppress an anchor rather than emit a None into the payload.

    ABLATION: remove the except in `_norm` and this raises ValueError out of a map
    refresh. Remove either `if p:` and the payload carries `robot_anchor: None`, which a
    renderer would read as a position.
    """
    cand = {
        "present": True, "calibration": _CAL_ROBIN, "pixel_size": None,
        "diagnostics": {},
        "rooms_raw": {
            "1": {"x0": "abc", "y0": 0, "x1": 100, "y1": 100},   # corner will not float
            "3": _ROOM_REAL,                                      # the good one survives
        },
        "robot": {"x": "nope", "y": 0, "a": 0},
        "dock": {"x": None, "y": None, "a": 0},
    }
    out = dreame_result_from_candidates(cand, present=True)
    assert [r["number"] for r in out["rooms"]] == [3], "one bad room must not cost the others"
    assert "robot_anchor" not in out, "an unprojectable robot emits no anchor, not a null one"
    assert "dock_anchor" not in out


def test_msr4q_a_saved_map_without_rooms_is_not_mistaken_for_geometry():
    """[MSR-4q] the `_1` entity exists but carries no rooms either — a saved map that was
    never segmented. The fallback must leave the breadcrumb unset rather than claim
    `saved_map_rooms`, and must NOT merge that entity's stale positions in.

    ABLATION: drop the `saved.get("rooms")` half of the condition and this goes red —
    `read` becomes "saved_map_rooms" over no geometry at all, and the stale robot
    position replaces the live one.
    """
    hass = _FakeHass({
        "camera.robin_map": _FakeState({
            "rooms": None,
            "calibration_points": _CAL_ROBIN,
            "vacuum_position": {"x": 100, "y": 200, "a": 90},
        }),
        "camera.robin_map_1": _FakeState({
            "rooms": None,                                    # saved map: also none
            "vacuum_position": {"x": -9999, "y": -9999, "a": 0},
        }),
    })
    out = dreame_camera_candidates(hass, {}, image_entity_id="camera.robin_map")
    assert out["present"] is True
    assert out["diagnostics"]["read"] is None, "no geometry was found, so claim none"
    assert not out["rooms_raw"]
    assert out["robot"] == {"x": 100, "y": 200, "a": 90}, "live position, untouched"

    # And the downstream consequence: no rooms -> not present, with a named reason.
    res = dreame_result_from_candidates(out, present=True)
    assert res["present"] is False and res["reason"] == "no_segmentation"


# ---------------------------------------------------------------------------
# [MSR-5] _structure_tree — the diagnostic shape dump, and its BOUNDS
#
# This is diagnostic-only code: both call sites run on the FAILURE path
# (`reason="no_parsed_map"` and `reason="no_pose"`) and write into
# `diag["structure"]`, so nothing a user sees depends on its output. That is an
# argument for testing its bounds, not against it. What the dump exists to do is
# SHOW where a parsed map or Room geometry actually lives when the duck-typed search
# misses, on a device nobody here owns — so the dump IS the bug report. Every
# statement uncovered in it was one of the limits that keeps it usable:
#
#   * the depth cap and the width cap, which are the whole "bounded" premise. An
#     unbounded walk of a live SDK graph produces a payload too large to read, and a
#     cyclic one would not terminate.
#   * the empty-sequence guard. Without it the list arm indexes `obj[0]`, so an empty
#     list RAISES. One call site wraps the dump in a blanket `except` that degrades it
#     to `{"error": "structure dump failed"}` — so a raise here does not crash the
#     integration, it silently costs the diagnostic the whole reason it was collected.
#   * the `__slots__` fallback. THIS IS RB-7 ONE FUNCTION OVER. `MSR-3e` pins that
#     lesson in `_walk`; `_structure_tree` carries its own copy of the fallback and
#     had no test, which is the shorter-copy shape — the same question answered twice
#     and fenced once.
#   * `show_skipped`, which is the only reason the second call site passes it: a
#     denylisted attr like `api` must still be VISIBLE as a skipped leaf, because the
#     sought data may sit behind exactly the attr the walk refuses to traverse.
# ---------------------------------------------------------------------------

class _Slotted:
    """A __slots__ object: no __dict__, so the __dict__ path finds nothing."""

    __slots__ = ("x0", "y0", "unset")

    def __init__(self):
        self.x0, self.y0 = 3, 4          # `unset` deliberately left unassigned


def test_structure_tree_depth_cap_returns_a_bare_type_name():
    """[MSR-5] At the depth cap the dump stops and names the type, nothing deeper.

    The cap is the dump's reason for existing in a bounded form at all: these roots
    are live vendor objects whose graphs reach hass, the event bus and back. Asserting
    only "it returned something" would hold for an unbounded walk too, so this asserts
    the FLOOR is a bare string at exactly the requested depth, and the level above it
    is still a dict.

    RED: delete `if depth >= max_depth: return tname` and the innermost level becomes
    a dict instead of the string "dict", recursing until the graph runs out.
    """
    deep = {"a": {"b": {"c": {"d": {"e": 1}}}}}

    out = _structure_tree(deep, max_depth=3)

    # depth 0 -> dict[1], 1 -> dict[1], 2 -> dict[1], then the cap names the type
    assert out == {"dict[1]": {"a": {"dict[1]": {"b": {"dict[1]": {"c": "dict"}}}}}}
    assert isinstance(out["dict[1]"]["a"]["dict[1]"]["b"]["dict[1]"]["c"], str), (
        "at the cap the dump must be a NAME, not another level"
    )


def test_structure_tree_empty_sequence_does_not_index_it():
    """[MSR-5b] An empty list is named, not indexed — the arm that stops a raise.

    The non-empty arm summarises `obj[0]` as representative of the whole sequence, so
    without the emptiness check that same expression raises IndexError on `[]`. A
    vendor payload with an empty `rooms` list is the ordinary case this dump is
    collected FOR, which is exactly when it must not fail.

    RED: delete `if not obj: return f"{tname}[0]"` and this raises IndexError. The
    tuple row is in because the arm covers both and `()` is the shape a parser is more
    likely to return.
    """
    assert _structure_tree([]) == "list[0]"
    assert _structure_tree(()) == "tuple[0]"
    # and the non-empty arm still summarises the FIRST member, not the count alone
    assert _structure_tree([{"x0": 1}]) == {"list[1]": {"dict[1]": {"x0": "int"}}}


def test_structure_tree_descends_into_a_slots_object():
    """[MSR-5c] RB-7 in `_structure_tree`: a __slots__ object is not an opaque leaf.

    `MSR-3e` pins this for `_walk`. `_structure_tree` has its own copy of the fallback
    and nothing exercised it, so the dump could have dead-ended on precisely the
    object a `__slots__`-using parser hands over — reporting `"_Slotted"` and no
    attributes, which reads exactly like an object with nothing in it.

    A declared-but-unassigned slot must also be skipped rather than raising:
    `getattr` on it throws AttributeError, and the generator swallows that per slot.

    RED: delete the `_slot_names` fallback and this returns the bare string
    "_Slotted"; delete the `except AttributeError: continue` inside `_slot_items` and
    the unassigned slot raises instead.
    """
    out = _structure_tree(_Slotted())

    assert out == {"_Slotted": {"x0": "int", "y0": "int"}}, (
        "both assigned slots visible, and the unset one absent rather than fatal"
    )


def test_structure_tree_width_cap_truncates_children():
    """[MSR-5d] The width cap, which bounds a WIDE object as the depth cap bounds a deep one.

    Asserted as an exact count rather than "fewer than all": an off-by-one in the
    `n >= max_children` test is the likely error, and `<=` versus `<` is invisible to
    a loose assertion.
    """
    class _Wide:
        def __init__(self):
            for i in range(50):
                setattr(self, f"attr{i:02d}", i)

    out = _structure_tree(_Wide(), max_children=5)

    assert len(out["_Wide"]) == 5, "exactly the budget, not 4 and not 6"
    assert set(out["_Wide"]) == {f"attr{i:02d}" for i in range(5)}, (
        "and it keeps the FIRST five, so the dump is reproducible between reads"
    )


def test_structure_tree_skips_dunder_attributes():
    """[MSR-5e] A dunder in an instance __dict__ is Python's business, not the map's.

    Reachable only for an object that explicitly sets one — `setattr(obj, "__x__", 1)`
    does land in `obj.__dict__` — so this guards against an odd vendor object rather
    than an everyday one. It earns a row because the dump has a width budget: internals
    crowding out real attributes is how the one field someone needed falls off the end.

    RED: delete `if k.startswith("__"): continue` and `__weird__` appears in the dump.

    Note the empty-dict rendering: `{"dict[0]": {}}`, not the string `"dict[0]"`. The
    bare-string form belongs to the list/tuple arm alone ([MSR-5b]), so an empty dict
    and an empty list read differently in a dump. Not a defect — an asymmetry worth
    knowing before reading one.
    """
    class _Odd:
        def __init__(self):
            self.rooms = {}

    obj = _Odd()
    setattr(obj, "__weird__", {"deep": 1})

    out = _structure_tree(obj)

    assert out == {"_Odd": {"rooms": {"dict[0]": {}}}}


def test_structure_tree_show_skipped_reveals_a_denylisted_attr_without_descending():
    """[MSR-5f] Both arms of `show_skipped`, because one alone proves nothing.

    The walk refuses to traverse `api`, `hass`, `client` and the rest — without that
    it would wander into the event bus. But the sought geometry may sit behind exactly
    one of those, so the dump taken when the search FAILS passes `show_skipped=True`
    to say "this attr exists, I did not look inside it". That is the difference
    between a bug report that points somewhere and one that looks like an empty object.

    Three assertions, and the first two are a pair: default OMITS the attr, and
    `show_skipped` names its TYPE without descending. A test of the second alone would
    pass if the flag did nothing and the attr were always shown.

    RED: delete the `if show_skipped:` arm and the second assertion fails; make it
    unconditional and the first fails; descend into it instead of naming the type and
    the third fails, with `secret` leaking into a diagnostic payload.
    """
    denylisted = sorted(_WALK_SKIP_ATTRS)[0]

    class _Holder:
        def __init__(self):
            self.rooms = {}
            setattr(self, denylisted, _Slotted())

    assert _structure_tree(_Holder()) == {"_Holder": {"rooms": {"dict[0]": {}}}}, (
        "by default a denylisted attr is invisible"
    )

    shown = _structure_tree(_Holder(), show_skipped=True)
    assert shown["_Holder"][denylisted] == "_Slotted (skipped)", (
        "its existence and type are reported, and the '(skipped)' says why no deeper"
    )
    assert "x0" not in str(shown), (
        "named, NOT descended into -- the denylist is still in force"
    )
