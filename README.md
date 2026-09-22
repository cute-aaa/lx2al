# lxmc2alcfg

Convert **lx-music** backup exports (`.lxmc` / `.json`) into **any-listen** songlist backup (`.alcfg`).

Zero dependencies (Python stdlib only). Supports gzip-compressed `.lxmc` and plain JSON.

## Why

[lx-music-desktop](https://github.com/lyswhut/lx-music-desktop) and [any-listen](https://github.com/any-listen/any-listen) both keep local playlists, but their backup formats are different. This tool migrates your lists from lx-music to any-listen without retyping songs.

## Install

### Windows (no Python needed)

Download `lx2al-windows-amd64.exe` from [Releases](https://github.com/cute-aaa/lx2al/releases) and run it:

```bat
lx2al-windows-amd64.exe G:\Download\lx_datas_v2.lxmc -o G:\Download\any-listen.converted.alcfg
```

### From source

```bash
python -m pip install -e .

# or just run without install
python -m lxmc2alcfg --help
```

Requires Python 3.10+.

### Build exe yourself

```powershell
powershell -File build_exe.ps1
# output: dist/lx2al.exe
```

## Usage

```bash
# lx-music full backup -> any-listen backup
python -m lxmc2alcfg G:/Download/lx_datas_v2.lxmc -o G:/Download/any-listen.converted.alcfg

# dry-run (print summary only)
python -m lxmc2alcfg lx_datas_v2.lxmc --dry-run

# plain JSON output (not gzipped)
python -m lxmc2alcfg lx_datas_v2.lxmc --json --pretty -o out.json
```

Import the resulting `.alcfg` in any-listen: **Settings → Backup → Import**.

## Supported lx-music input

| `type` | Meaning |
|---|---|
| `allData_v2` | Full backup (settings + playlists) — default export `lx_datas_v2.lxmc` |
| `allData` | Legacy full backup (≤ 0.6.2) |
| `playList_v2` | Playlists only (`lx_list.lxmc`) |
| `playList` | Legacy playlists only |
| `playListPart_v2` | Single-list part export |

Files may be gzip-compressed (`.lxmc`) or plain UTF-8 JSON.

## Field mapping

| lx-music | any-listen |
|---|---|
| `playList[].list[]` | `songlist.data.*.list[]` |
| `id: default` / `list__name_default` | `defaultList` |
| `id: love` / `list__name_love` | `loveList` |
| other lists | `userList[]` (`type: "general"`) |
| song `meta.songId` | song `id` + `meta.musicId` |
| song `source` | `meta.source` |
| `meta.qualitys[]` / `meta._qualitys` | `meta.qualitys` (`{type: {sizeStr, hash?}}`) |
| `interval` `"mm:ss"` | `meta._interval` (seconds) |
| list `source` / `sourceListId` | preserved in list `meta.desc` as `lx:<source>:<sourceListId>` |
| source extras (`hash`, `albumId`, `copyrightId`, …) | kept on `meta` (any-listen online meta allows extra keys) |

## Output shape

Matches any-listen `AnyListen.BackupData` / `List.ListDataFull` (`songlist.version = 1`):

```json
{
  "songlist": {
    "version": 1,
    "data": {
      "defaultList": { "id": "default", "name": "default", "type": "default", "meta": {}, "parentId": null, "list": [] },
      "loveList": { "id": "love", "name": "love", "type": "default", "meta": {}, "parentId": null, "list": [] },
      "userList": []
    }
  }
}
```

## Notes / limits

- Settings (`setting`) are **not** converted — any-listen settings differ. Use any-listen's own settings UI.
- Online list *links* (lx `source` + `sourceListId`) are recorded in `meta.desc`; songs themselves are materialized as a normal `general` list. any-listen list types `online` / `local` / `remote` are not synthesized.
- `temp` lists become a user list named `temp`.
- Song ids use lx `meta.songId` (without `kg_…` hash suffix). Same song appearing in several playlists is expected and kept.

## Development

```bash
python -m unittest discover -s tests -v
```

Format references:

- any-listen types: [`packages/shared/types/types/list.d.ts`](https://github.com/any-listen/any-listen/blob/main/packages/shared/types/types/list.d.ts), [`music.d.ts`](https://github.com/any-listen/any-listen/blob/main/packages/shared/types/types/music.d.ts)
- lx-music types: [`src/common/types/list.d.ts`](https://github.com/lyswhut/lx-music-desktop/blob/master/src/common/types/list.d.ts), [`music.d.ts`](https://github.com/lyswhut/lx-music-desktop/blob/master/src/common/types/music.d.ts)
- lx-music export UI: [`SettingBackup.vue`](https://github.com/lyswhut/lx-music-desktop/blob/master/src/renderer/views/Setting/components/SettingBackup.vue)

## License

MIT
