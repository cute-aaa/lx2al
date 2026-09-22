"""Core conversion: lx-music list export -> any-listen songlist backup.

Supported lx-music input shapes (gzip or plain JSON):
  - allData_v2   {type, setting, playList: List[]}
  - allData      (legacy) {type, defaultList?, playList?, setting}
  - playList_v2  {type, data: List[]}
  - playList     (legacy) {type, data: List[]}

Output is any-listen BackupData partial:
  {"songlist": {"version": 1, "data": {"defaultList", "loveList", "userList"}}}
Reference types:
  - https://github.com/any-listen/any-listen (List.ListDataFull, Music.MusicInfo)
  - https://github.com/lyswhut/lx-music-desktop (LX.List, LX.Music)
"""

from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

LIST_NAME_MAP = {
    "list__name_default": "default",
    "list__name_love": "love",
    "list__name_temp": "temp",
    "临时列表": "temp",
    "default": "default",
    "love": "love",
    "试听列表": "default",
    "我的收藏": "love",
}

SYSTEM_LIST_IDS = {"default": "default", "love": "love", "temp": "temp"}


def to_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def interval_to_seconds(interval: Any) -> int:
    if not interval or not isinstance(interval, str):
        return 0
    parts = interval.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return 0


def convert_qualitys(meta: dict[str, Any]) -> dict[str, Any]:
    """lx qualitys is [{type,size,hash?}...] / _qualitys object -> any-listen {type: {sizeStr, hash?}}."""
    result: dict[str, Any] = {}

    src = meta.get("_qualitys")
    if isinstance(src, dict) and src:
        for qtype, qv in src.items():
            if not isinstance(qv, dict):
                qv = {"size": qv}
            item: dict[str, Any] = {"sizeStr": to_str(qv.get("size") or qv.get("sizeStr") or "")}
            h = qv.get("hash")
            if h:
                item["hash"] = to_str(h)
            result[str(qtype)] = item
        return result

    qlist = meta.get("qualitys")
    if isinstance(qlist, list):
        for q in qlist:
            if not isinstance(q, dict):
                continue
            qtype = to_str(q.get("type"))
            if not qtype:
                continue
            item = {"sizeStr": to_str(q.get("size") or q.get("sizeStr") or "")}
            h = q.get("hash")
            if h:
                item["hash"] = to_str(h)
            result[qtype] = item
    elif isinstance(qlist, dict):
        for qtype, qv in qlist.items():
            if isinstance(qv, dict):
                item = {"sizeStr": to_str(qv.get("size") or qv.get("sizeStr") or "")}
                h = qv.get("hash")
                if h:
                    item["hash"] = to_str(h)
            else:
                item = {"sizeStr": to_str(qv)}
            result[str(qtype)] = item
    return result


def _music_id(meta: dict[str, Any], lx_song: dict[str, Any]) -> str:
    song_id = meta.get("songId")
    if song_id is None:
        song_id = meta.get("musicId")
    if song_id is None:
        raw = to_str(lx_song.get("id") or "")
        # lx online ids: "mg_123", "305029273_HASH", "tx_xxx", "kw_123"
        if raw.startswith(("mg_", "kw_", "wy_", "tx_", "kg_")):
            raw = raw.split("_", 1)[-1]
        elif "_" in raw:
            raw = raw.split("_", 1)[0]
        song_id = raw
    return to_str(song_id)


# lx source-specific extras worth preserving on any-listen online meta
# (MusicInfoMeta_online allows [key: string] extras)
_KEEP_META_KEYS = (
    "albumId",
    "albumAudioId",
    "hash",
    "copyrightId",
    "lrcUrl",
    "mrcUrl",
    "trcUrl",
    "strMediaMid",
    "albumMid",
    "id",
    "fileName",
    "ext",
    "bitrateLabel",
    "sizeStr",
    "year",
    "trackNo",
    "discNo",
)


def convert_song(lx_song: Any) -> dict[str, Any]:
    if not isinstance(lx_song, dict):
        raise TypeError(f"song must be object, got {type(lx_song).__name__}")

    meta = lx_song.get("meta") if isinstance(lx_song.get("meta"), dict) else {}
    source = to_str(lx_song.get("source") or meta.get("source") or "")
    music_id = _music_id(meta, lx_song)
    interval = lx_song.get("interval")
    interval_str = to_str(interval) if interval is not None else None

    out_meta: dict[str, Any] = {
        "albumName": to_str(meta.get("albumName") or ""),
        "source": source,
        "musicId": music_id,
        "qualitys": convert_qualitys(meta),
        "createTime": 0,
        "posTime": 0,
        "updateTime": 0,
    }

    pic = meta.get("picUrl")
    if pic:
        out_meta["picUrl"] = to_str(pic)

    if interval_str is not None:
        out_meta["_interval"] = interval_to_seconds(interval_str)

    for key in _KEEP_META_KEYS:
        if key in meta and meta[key] is not None and key != "id":
            val = meta[key]
            if isinstance(val, (str, int, float, bool, dict, list)):
                out_meta[key] = val
            else:
                out_meta[key] = to_str(val)
    # lx tx uses meta.id as numeric songId; keep only if it differs from musicId string form
    if "id" in meta and meta["id"] is not None:
        meta_id = to_str(meta["id"])
        if meta_id and meta_id != music_id:
            out_meta["lxId"] = meta_id

    # optional _qualitys mirror (array form) is not part of any-listen; skip
    is_local = source == "local" or bool(meta.get("filePath"))

    if is_local:
        return {
            "id": music_id or to_str(lx_song.get("id") or ""),
            "name": to_str(lx_song.get("name") or ""),
            "singer": to_str(lx_song.get("singer") or ""),
            "isLocal": True,
            "interval": interval_str,
            "meta": {
                "musicId": music_id or to_str(lx_song.get("id") or ""),
                "albumName": to_str(meta.get("albumName") or ""),
                "filePath": to_str(meta.get("filePath") or ""),
                "ext": to_str(meta.get("ext") or ""),
                "bitrateLabel": None,
                "sizeStr": to_str(meta.get("sizeStr") or ""),
                "deviceId": to_str(meta.get("deviceId") or ""),
                "createTime": 0,
                "updateTime": 0,
                "posTime": 0,
                **({"picUrl": to_str(pic)} if pic else {}),
            },
        }

    return {
        "id": music_id,
        "name": to_str(lx_song.get("name") or ""),
        "singer": to_str(lx_song.get("singer") or ""),
        "isLocal": False,
        "interval": interval_str,
        "meta": out_meta,
    }


def _now_ms() -> int:
    return int(time.time() * 1000)


def _default_love_meta(now_ms: int, song_count: int) -> dict[str, Any]:
    return {
        "playCount": 0,
        "playTime": 0,
        "createTime": now_ms,
        "updateTime": now_ms,
        "posTime": 0,
        "songCount": song_count,
    }


def _user_meta(now_ms: int, song_count: int, desc: str = "") -> dict[str, Any]:
    return {
        "createTime": now_ms,
        "desc": desc,
        "playCount": 0,
        "songCount": song_count,
        "pic": "",
        "posTime": now_ms,
        "updateTime": now_ms,
    }


def _normalize_list_name(raw_name: str, raw_id: str) -> tuple[str, str]:
    """Return (kind, display_name) where kind is default|love|temp|user."""
    mapped = LIST_NAME_MAP.get(raw_name)
    if mapped in SYSTEM_LIST_IDS:
        return mapped, mapped
    if raw_id in SYSTEM_LIST_IDS:
        return raw_id, SYSTEM_LIST_IDS[raw_id]
    if raw_name.startswith("list__name_"):
        key = raw_name[len("list__name_") :]
        if key in SYSTEM_LIST_IDS:
            return key, SYSTEM_LIST_IDS[key]
    return "user", raw_name


def _list_provenance_desc(lx_pl: dict[str, Any]) -> str:
    source = to_str(lx_pl.get("source") or "")
    source_list_id = to_str(lx_pl.get("sourceListId") or "")
    if not source and not source_list_id:
        return ""
    parts = ["lx"]
    if source:
        parts.append(source)
    if source_list_id:
        parts.append(source_list_id)
    return ":".join(parts)


def convert_playlist(lx_pl: Any, kind: str, now_ms: int) -> dict[str, Any]:
    if not isinstance(lx_pl, dict):
        raise TypeError(f"playlist must be object, got {type(lx_pl).__name__}")

    raw_id = to_str(lx_pl.get("id") or "")
    raw_name = to_str(lx_pl.get("name") or "")
    norm_kind, display_name = _normalize_list_name(raw_name, raw_id)

    songs_raw = lx_pl.get("list")
    if songs_raw is None:
        songs_raw = []
    if not isinstance(songs_raw, list):
        raise TypeError("playlist.list must be an array")
    songs = [convert_song(s) for s in songs_raw]
    n = len(songs)

    if kind in ("default", "love"):
        list_id = kind
        name = kind
        list_type = "default"
        meta = _default_love_meta(now_ms, n)
    elif kind == "temp":
        # any-listen ListDataFull does not export lastPlayList/temp; fold into user list
        list_id = "temp"
        name = "temp"
        list_type = "general"
        meta = _user_meta(now_ms, n, desc=_list_provenance_desc(lx_pl))
    else:
        list_id = raw_id or display_name or "user_list"
        name = display_name or list_id
        list_type = "general"
        meta = _user_meta(now_ms, n, desc=_list_provenance_desc(lx_pl))

    return {
        "id": list_id,
        "name": name,
        "type": list_type,
        "meta": meta,
        "parentId": None,
        "list": songs,
    }


def _extract_play_lists(lx: dict[str, Any]) -> list[Any]:
    lx_type = to_str(lx.get("type") or "")

    if lx_type == "allData_v2":
        pl = lx.get("playList")
        return list(pl) if isinstance(pl, list) else []

    if lx_type == "allData":
        # legacy: may have defaultList object and/or playList array
        out: list[Any] = []
        pl = lx.get("playList")
        if isinstance(pl, list):
            out.extend(pl)
        elif isinstance(pl, dict):
            out.extend(pl.get("list") or [])
        default_list = lx.get("defaultList")
        if isinstance(default_list, dict) and default_list.get("list") is not None:
            # only add if not already present
            if not any(isinstance(x, dict) and x.get("id") == "default" for x in out):
                out.insert(0, {"id": "default", "name": "list__name_default", "list": default_list.get("list") or []})
        love_list = lx.get("loveList")
        if isinstance(love_list, dict) and love_list.get("list") is not None:
            if not any(isinstance(x, dict) and x.get("id") == "love" for x in out):
                out.append({"id": "love", "name": "list__name_love", "list": love_list.get("list") or []})
        return out

    if lx_type in ("playList_v2", "playList"):
        data = lx.get("data")
        if isinstance(data, list):
            return list(data)
        if isinstance(data, dict):
            out = []
            for key in ("defaultList", "loveList"):
                if isinstance(data.get(key), dict):
                    item = dict(data[key])
                    item.setdefault("id", key.replace("List", "") if key != "defaultList" else "default")
                    if key == "defaultList":
                        item.setdefault("id", "default")
                        item.setdefault("name", "list__name_default")
                    else:
                        item.setdefault("id", "love")
                        item.setdefault("name", "list__name_love")
                    out.append(item)
            user = data.get("userList") or data.get("userLists")
            if isinstance(user, list):
                out.extend(user)
            return out

    if lx_type == "playListPart_v2":
        data = lx.get("data")
        if isinstance(data, dict):
            return [data]

    raise ValueError(f"unsupported lx-music data type: {lx_type or '(missing type)'}")


def detect_lx_type(lx: Any) -> str:
    if isinstance(lx, dict) and isinstance(lx.get("type"), str):
        return lx["type"]
    return ""


def convert(lx: Any, *, now_ms: int | None = None) -> dict[str, Any]:
    """Convert parsed lx-music data into any-listen songlist BackupData."""
    if not isinstance(lx, dict):
        raise TypeError("lx-music data must be a JSON object")

    lx_type = detect_lx_type(lx)
    supported = {"allData_v2", "allData", "playList_v2", "playList", "playListPart_v2"}
    if lx_type not in supported:
        raise ValueError(
            f"unsupported lx-music type {lx_type!r}; supported: {', '.join(sorted(supported))}"
        )

    if now_ms is None:
        now_ms = _now_ms()

    play_lists = _extract_play_lists(lx)

    default_list: dict[str, Any] | None = None
    love_list: dict[str, Any] | None = None
    user_lists: list[dict[str, Any]] = []

    for pl in play_lists:
        if not isinstance(pl, dict):
            continue
        raw_id = to_str(pl.get("id") or "")
        raw_name = to_str(pl.get("name") or "")
        kind, _ = _normalize_list_name(raw_name, raw_id)
        if kind == "default":
            default_list = convert_playlist(pl, "default", now_ms)
        elif kind == "love":
            love_list = convert_playlist(pl, "love", now_ms)
        else:
            user_lists.append(convert_playlist(pl, "user", now_ms))

    if default_list is None:
        default_list = {
            "id": "default",
            "name": "default",
            "type": "default",
            "meta": _default_love_meta(now_ms, 0),
            "parentId": None,
            "list": [],
        }
    if love_list is None:
        love_list = {
            "id": "love",
            "name": "love",
            "type": "default",
            "meta": _default_love_meta(now_ms, 0),
            "parentId": None,
            "list": [],
        }

    # de-dup user list ids (keep first, suffix later ones)
    seen_ids: dict[str, int] = {}
    for item in user_lists:
        base = item["id"]
        if base in seen_ids:
            seen_ids[base] += 1
            item["id"] = f"{base}_{seen_ids[base]}"
        else:
            seen_ids[base] = 1

    return {
        "songlist": {
            "version": 1,
            "data": {
                "defaultList": default_list,
                "loveList": love_list,
                "userList": user_lists,
            },
        }
    }


def load_lx_data(path: str | Path) -> dict[str, Any]:
    """Load lx-music export from .lxmc/.json (gzip or plain)."""
    p = Path(path)
    raw = p.read_bytes()
    data = raw
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        data = gzip.decompress(raw)
    text = data.decode("utf-8-sig")
    return json.loads(text)


def save_alcfg(data: dict[str, Any], path: str | Path) -> Path:
    """Write any-listen .alcfg (gzip-compressed JSON, same as saveAnyListenConfigFile)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(p, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(text.encode("utf-8"))
    return p


def save_json(data: dict[str, Any], path: str | Path, *, indent: int | None = 2) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    return p


def convert_file(
    src: str | Path,
    dst: str | Path,
    *,
    pretty: bool = False,
    gzip_out: bool | None = None,
) -> dict[str, Any]:
    """Convert lx-music file to any-listen file. Returns the converted data."""
    lx = load_lx_data(src)
    out = convert(lx)
    dst_path = Path(dst)
    if gzip_out is None:
        gzip_out = dst_path.suffix.lower() == ".alcfg" or dst_path.name.lower().endswith(".alcfg")
    if gzip_out:
        save_alcfg(out, dst_path)
    else:
        save_json(out, dst_path, indent=2 if pretty else None)
    return out
