"""Unit tests for mapping/map_source_runtime.py — the map_state_source runtime locators.

The HA-aware glue itself (registry/file/hass.data access) needs a live deploy, but the
extraction + version guard + presence gate + the defensive Roborock introspector are
PURE given injected plain data — tested here without Home Assistant.

[MSR-1] eufy_result_from_store: version guard, presence gate, extraction, degradation.
[MSR-2] roborock_result_from_candidates / rooms_from_mapdata / find_mapdata: MapData
        located + projected via the parser's to_img transform, no-go-immune, no-geometry,
        presence gate, structure dump — always with a diagnostics breadcrumb.
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


class _Obstacle:
    def __init__(self, x, y, type_):
        self.x, self.y, self.type = x, y, type_


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
        obstacles=[_Obstacle(500, 500, "cable")],
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
