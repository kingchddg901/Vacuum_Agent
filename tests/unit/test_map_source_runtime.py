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
"""
import base64

from custom_components.eufy_vacuum.mapping.map_source_runtime import (
    eufy_live_pose_from_candidates,
    eufy_mapdata_from_candidates,
    eufy_mapdata_obj_from_candidates,
    eufy_render_data_from_store,
    eufy_result_from_mapdata,
    eufy_result_from_store,
    find_mapdata,
    find_roomlike_collection,
    overlays_from_mapdata,
    _mapdata_projector,
    roborock_result_from_candidates,
    rooms_from_mapdata,
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
    assert out["present"] is True and out["format"] == "eufy_room_pixels_v1"
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
