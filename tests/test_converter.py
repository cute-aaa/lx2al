"""Unit tests for lxmc2alcfg. Run: python -m unittest discover -s tests -v"""

from __future__ import annotations

import gzip
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lxmc2alcfg.converter import (  # noqa: E402
    convert,
    convert_qualitys,
    convert_song,
    detect_lx_type,
    interval_to_seconds,
    load_lx_data,
    save_alcfg,
)


def sample_all_data_v2() -> dict:
    return {
        "type": "allData_v2",
        "setting": {"version": "2.1.0"},
        "playList": [
            {"id": "default", "name": "list__name_default", "list": [
                {
                    "id": "mg_1108169795",
                    "name": "Careless Whisper",
                    "singer": "Wham!",
                    "source": "mg",
                    "interval": "05:02",
                    "meta": {
                        "songId": "1108169795",
                        "albumName": "Schmusesongs Vol. 1",
                        "picUrl": "http://example.com/a.jpg",
                        "qualitys": [
                            {"type": "128k", "size": "4.54 MB"},
                            {"type": "320k", "size": "11.33 MB"},
                        ],
                        "_qualitys": {
                            "128k": {"size": "4.54 MB"},
                            "320k": {"size": "11.33 MB"},
                        },
                        "albumId": "1113474514",
                        "copyrightId": "6005971FQKT",
                        "lrcUrl": "https://example.com/a.lrc",
                    },
                }
            ]},
            {"id": "love", "name": "list__name_love", "list": [
                {
                    "id": "7956183_DF1AECC7493160BA15FA71120F9C4A3F",
                    "name": "记·念 (Live)",
                    "singer": "雷雨心",
                    "source": "kg",
                    "interval": "02:45",
                    "meta": {
                        "songId": 7956183,
                        "albumName": "中国好歌曲第二季",
                        "picUrl": None,
                        "qualitys": [
                            {"type": "128k", "size": "2.53 MB", "hash": "DF1A"},
                        ],
                        "_qualitys": {
                            "128k": {"size": "2.53 MB", "hash": "DF1A"},
                        },
                        "albumId": "544792",
                        "hash": "DF1A",
                    },
                }
            ]},
            {
                "id": "wy_abc",
                "name": "sure",
                "source": "wy",
                "sourceListId": "2787556404",
                "locationUpdateTime": None,
                "list": [],
            },
            {
                "id": "temp",
                "name": "临时列表",
                "meta": {"id": "x"},
                "list": [],
            },
        ],
    }


class TestHelpers(unittest.TestCase):
    def test_interval_mmss(self):
        self.assertEqual(interval_to_seconds("03:52"), 232)
        self.assertEqual(interval_to_seconds("05:02"), 302)

    def test_interval_hhmmss(self):
        self.assertEqual(interval_to_seconds("01:02:03"), 3723)

    def test_interval_bad(self):
        self.assertEqual(interval_to_seconds(None), 0)
        self.assertEqual(interval_to_seconds(""), 0)
        self.assertEqual(interval_to_seconds("abc"), 0)
        self.assertEqual(interval_to_seconds(12), 0)

    def test_qualitys_from_list(self):
        out = convert_qualitys({"qualitys": [{"type": "128k", "size": "1 MB", "hash": "H"}]})
        self.assertEqual(out, {"128k": {"sizeStr": "1 MB", "hash": "H"}})

    def test_qualitys_from_object(self):
        out = convert_qualitys({"_qualitys": {"flac": {"size": "20 MB"}}})
        self.assertEqual(out, {"flac": {"sizeStr": "20 MB"}})

    def test_qualitys_empty(self):
        self.assertEqual(convert_qualitys({}), {})


class TestConvertSong(unittest.TestCase):
    def test_basic_fields(self):
        s = convert_song(sample_all_data_v2()["playList"][0]["list"][0])
        self.assertEqual(s["id"], "1108169795")
        self.assertEqual(s["name"], "Careless Whisper")
        self.assertFalse(s["isLocal"])
        self.assertEqual(s["interval"], "05:02")
        self.assertEqual(s["meta"]["musicId"], "1108169795")
        self.assertEqual(s["meta"]["source"], "mg")
        self.assertEqual(s["meta"]["_interval"], 302)
        self.assertEqual(s["meta"]["copyrightId"], "6005971FQKT")
        self.assertEqual(s["meta"]["qualitys"]["128k"]["sizeStr"], "4.54 MB")

    def test_kg_hash(self):
        s = convert_song(sample_all_data_v2()["playList"][1]["list"][0])
        self.assertEqual(s["id"], "7956183")
        self.assertEqual(s["meta"]["hash"], "DF1A")
        self.assertEqual(s["meta"]["qualitys"]["128k"]["hash"], "DF1A")

    def test_missing_meta(self):
        # kg-style lx id without meta: "<songId>_<hash>" -> songId
        s = convert_song({"id": "305029273_AABBCC", "name": "n", "singer": "s", "source": "kg", "interval": None})
        self.assertEqual(s["meta"]["musicId"], "305029273")
        self.assertEqual(s["meta"]["qualitys"], {})
        self.assertIsNone(s["interval"])

    def test_prefixed_id_without_meta(self):
        s = convert_song({"id": "mg_99", "name": "n", "singer": "s", "source": "mg"})
        self.assertEqual(s["meta"]["musicId"], "99")

    def test_local(self):
        s = convert_song({
            "id": "/a/b.mp3",
            "name": "n",
            "singer": "s",
            "source": "local",
            "interval": "01:00",
            "meta": {"songId": "/a/b.mp3", "filePath": "/a/b.mp3", "ext": "mp3"},
        })
        self.assertTrue(s["isLocal"])
        self.assertEqual(s["meta"]["filePath"], "/a/b.mp3")


class TestConvertAllDataV2(unittest.TestCase):
    def test_structure(self):
        out = convert(sample_all_data_v2(), now_ms=1000)
        self.assertIn("songlist", out)
        self.assertEqual(out["songlist"]["version"], 1)
        data = out["songlist"]["data"]
        self.assertEqual(set(data), {"defaultList", "loveList", "userList"})
        self.assertEqual(data["defaultList"]["id"], "default")
        self.assertEqual(data["loveList"]["id"], "love")
        self.assertEqual(data["defaultList"]["type"], "default")
        self.assertEqual(data["defaultList"]["meta"]["songCount"], 1)
        self.assertEqual(data["loveList"]["meta"]["songCount"], 1)

    def test_user_list_provenance(self):
        out = convert(sample_all_data_v2(), now_ms=1000)
        users = out["songlist"]["data"]["userList"]
        sure = next(u for u in users if u["name"] == "sure")
        self.assertEqual(sure["type"], "general")
        self.assertIn("wy", sure["meta"]["desc"])
        self.assertIn("2787556404", sure["meta"]["desc"])

    def test_temp_becomes_user(self):
        out = convert(sample_all_data_v2(), now_ms=1000)
        names = [u["name"] for u in out["songlist"]["data"]["userList"]]
        self.assertIn("temp", names)


class TestOtherInputTypes(unittest.TestCase):
    def test_play_list_v2(self):
        data = {
            "type": "playList_v2",
            "data": sample_all_data_v2()["playList"][:2],
        }
        out = convert(data, now_ms=1)
        self.assertEqual(out["songlist"]["data"]["defaultList"]["meta"]["songCount"], 1)
        self.assertEqual(out["songlist"]["data"]["userList"], [])

    def test_legacy_all_data(self):
        data = {
            "type": "allData",
            "setting": {},
            "defaultList": {"list": [{"id": "a", "name": "A", "singer": "s", "source": "kw", "meta": {}}]},
            "playList": [],
        }
        out = convert(data, now_ms=1)
        self.assertEqual(out["songlist"]["data"]["defaultList"]["meta"]["songCount"], 1)

    def test_unsupported_type(self):
        with self.assertRaises(ValueError):
            convert({"type": "setting_v2", "data": {}})

    def test_detect(self):
        self.assertEqual(detect_lx_type(sample_all_data_v2()), "allData_v2")
        self.assertEqual(detect_lx_type({}), "")


class TestFileIO(unittest.TestCase):
    def test_gzip_roundtrip(self, tmp: Path | None = None):
        base = Path(__file__).parent / "fixtures"
        base.mkdir(exist_ok=True)
        raw_path = base / "_tmp_in.json"
        gz_path = base / "_tmp_in.lxmc"
        out_path = base / "_tmp_out.alcfg"

        payload = sample_all_data_v2()
        raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        raw = raw_path.read_bytes()
        with open(gz_path, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as g:
            g.write(raw)

        loaded = load_lx_data(gz_path)
        self.assertEqual(loaded["type"], "allData_v2")

        converted = convert(loaded, now_ms=2)
        save_alcfg(converted, out_path)
        # decompress and check
        with gzip.open(out_path, "rb") as g:
            back = json.loads(g.read().decode("utf-8"))
        self.assertEqual(back["songlist"]["data"]["defaultList"]["meta"]["songCount"], 1)

        for p in (raw_path, gz_path, out_path):
            p.unlink(missing_ok=True)


class TestEmptyLists(unittest.TestCase):
    def test_empty_play_list(self):
        out = convert({"type": "allData_v2", "setting": {}, "playList": []}, now_ms=9)
        data = out["songlist"]["data"]
        self.assertEqual(data["defaultList"]["list"], [])
        self.assertEqual(data["loveList"]["list"], [])
        self.assertEqual(data["userList"], [])
        self.assertEqual(data["defaultList"]["meta"]["songCount"], 0)


if __name__ == "__main__":
    unittest.main()
