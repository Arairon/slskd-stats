# slskd-stats

`slskd-stats` is a script that parses the `transfers.db` file from a [slskd](https://github.com/slskd/slskd) container and provides detailed statistics about your uploads and downloads, including the ones you've hidden from web UI. The `transfers.db` file is typically located at `/app/data/transfers.db` in the slskd container.

Thanks [Player6734](https://github.com/Player6734/slskd-stats) for the inspiration.

## Features

- Displays total uploaded and downloaded data.
- Shows the number of completed and failed transfers.
- Calculates average upload and download speeds.
- Lists the top users by data transferred.
- Lists the top files, folders and formats by number of transfers.
- Reports common errors encountered during transfers.
- Outputs stats in plain text or JSON format.
- Reads a live `transfers.db` in place, without stopping slskd.

## Requirements

- Python 3.6 or higher

## Usage

1. Download the script
2. Get the transfers.db file (typically located at `/app/data/transfers.db` in the slskd container. If you do not have the /app directory mounted, then you can use `docker cp <container_id>:/app/data/transfers.db ./transfers.db` to copy the file directly from the container)
3. Run the script. The script will attempt to open a `./transfers.db` file. You can change the desired file with the `-f path/to/file` flag. (You can also use `-j` to get json instead of plain text and `-r` to get raw info)

### Flags

| Flag | Description |
| --- | --- |
| `-f`, `--file` | Path to the `transfers.db` to read (default `./transfers.db`) |
| `-j`, `--json` | Output json instead of plain text |
| `-r`, `--rawjson` | Output raw, unformatted stats. Requires `-j` |
| `-n`, `--top` | How many entries to show in each top list (default `5`) |

### Reading a live database

You can point `-f` straight at the database slskd is using, e.g. a bind mount or
an NFS/SMB share of the container's data directory - the file is never written to:

```sh
./main.py -f /path/to/slskd/data/transfers.db
```

The database is opened read-only. If sqlite refuses that (a running slskd leaves a
hot `transfers.db-wal`, which sqlite may need to write to before it can read it, and
the files are usually owned by root), the script copies `transfers.db` and its `-wal`
/ `-shm` sidecars to a temporary directory and reads the copy instead, so recent
transfers still show up. It prints a `note:` to stderr when it does this.

## Output example

Both examples below are the real output of the script against a small generated
database, trimmed to two entries per list in the json case.

Default:

```plain
===== slskd-stats =====
= Upload =
Total uploaded:	42.35 GB	(1932 files)
Total failed:	266
Average speed:	1.36 MB/s
Unique files:	93
Unique users:	8
Top users:
  quietstorm:   	 5.97 GB
  hasko:        	 5.55 GB
  MeGUMaNiAC:   	 5.37 GB
  n0isefloor:   	 5.30 GB
  psyfarkledon: 	 5.25 GB
Top files:
  158 x  4.33 GB  Discovery\01 - Track 1.flac
  108 x  2.23 GB  Homework\01 - Track 1.flac
   83 x  2.58 GB  Cross\01 - Track 1.flac
   83 x  2.55 GB  Discovery\02 - Track 2.flac
   62 x 31.94 MB  Discovery\cover.jpg
Top folders:
  628 x 15.99 GB  Music (FLAC)\Daft Punk\Discovery
  434 x  9.93 GB  Music (FLAC)\Daft Punk\Homework
  300 x  8.15 GB  Music (FLAC)\Justice\Cross
  250 x  2.15 GB  Music (MP3)\Various Artists\Chillout Sessions
  185 x  5.12 GB  Music (FLAC)\Air\Moon Safari
Top formats:
  1391 x  39.11 GB  flac
   347 x   3.15 GB  mp3
   194 x 100.94 MB  jpg

= Download =
Total downloaded:	8.34 GB	(398 files)
Total failed:	56
Average speed:	1.34 MB/s
Unique files:	88
Unique users:	8
Top users:
  psyfarkledon: 	 1.25 GB
  winivb:       	 1.17 GB
  quietstorm:   	 1.05 GB
  MeGUMaNiAC:   	 1.03 GB
  lolmakermine: 	 1018.56 MB
Top files:
  35 x 860.56 MB  Discovery\01 - Track 1.flac
  19 x 475.08 MB  Discovery\02 - Track 2.flac
  18 x 465.48 MB  Cross\01 - Track 1.flac
  17 x 517.00 MB  Homework\01 - Track 1.flac
  14 x 166.13 MB  Chillout Sessions\01 - Track 1.mp3
Top folders:
  131 x   3.09 GB  Music (FLAC)\Daft Punk\Discovery
   87 x   2.12 GB  Music (FLAC)\Daft Punk\Homework
   62 x   1.54 GB  Music (FLAC)\Justice\Cross
   51 x 392.45 MB  Music (MP3)\Various Artists\Chillout Sessions
   39 x   1.04 GB  Music (FLAC)\Air\Moon Safari
Top formats:
  287 x   7.77 GB  flac
   71 x 567.23 MB  mp3
   40 x  19.12 MB  jpg

= Errors =
  "The wait timed out":	70
  "Too many files requested":	68
  "Transfer rejected: Cancelled":	66
  "User offline":	61
  "Failed to upload file":	57
```

Top files show the last two path components; the full path is in the json output.
The count is how many times that file, folder or format was transferred, and the
size next to it is the total moved across those transfers.

JSON:

```json
{
  "upload": {
    "speed": "1.36 MB/s",
    "completed": 1932,
    "errored": 266,
    "uniqueUsers": 8,
    "uniqueFiles": 93,
    "users": {
      "quietstorm": "5.97 GB",
      "hasko": "5.55 GB"
    },
    "files": [
      {
        "name": "Music (FLAC)\\Daft Punk\\Discovery\\01 - Track 1.flac",
        "count": 158,
        "size": "4.33 GB"
      },
      {
        "name": "Music (FLAC)\\Daft Punk\\Homework\\01 - Track 1.flac",
        "count": 108,
        "size": "2.23 GB"
      }
    ],
    "folders": [
      {
        "name": "Music (FLAC)\\Daft Punk\\Discovery",
        "count": 628,
        "size": "15.99 GB"
      },
      {
        "name": "Music (FLAC)\\Daft Punk\\Homework",
        "count": 434,
        "size": "9.93 GB"
      }
    ],
    "formats": [
      {
        "name": "flac",
        "count": 1391,
        "size": "39.11 GB"
      },
      {
        "name": "mp3",
        "count": 347,
        "size": "3.15 GB"
      }
    ],
    "size": "42.35 GB"
  },
  "download": {
    "speed": "1.34 MB/s",
    "completed": 398,
    "errored": 56,
    "uniqueUsers": 8,
    "uniqueFiles": 88,
    "users": {
      "psyfarkledon": "1.25 GB",
      "winivb": "1.17 GB"
    },
    "files": [
      {
        "name": "Music (FLAC)\\Daft Punk\\Discovery\\01 - Track 1.flac",
        "count": 35,
        "size": "860.56 MB"
      },
      {
        "name": "Music (FLAC)\\Daft Punk\\Discovery\\02 - Track 2.flac",
        "count": 19,
        "size": "475.08 MB"
      }
    ],
    "folders": [
      {
        "name": "Music (FLAC)\\Daft Punk\\Discovery",
        "count": 131,
        "size": "3.09 GB"
      },
      {
        "name": "Music (FLAC)\\Daft Punk\\Homework",
        "count": 87,
        "size": "2.12 GB"
      }
    ],
    "formats": [
      {
        "name": "flac",
        "count": 287,
        "size": "7.77 GB"
      },
      {
        "name": "mp3",
        "count": 71,
        "size": "567.23 MB"
      }
    ],
    "size": "8.34 GB"
  },
  "errors": {
    "The wait timed out": 70,
    "Too many files requested": 68
  }
}
```

`users` stays a name-keyed object, as it always has been, so existing consumers of
`-j` keep working. The new `files`, `folders` and `formats` sections are arrays
instead: they are ranked, and each entry carries both a count and a size, neither of
which fits a single key/value pair. `uniqueUsers` and `uniqueFiles` are additive.
