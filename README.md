# slskd-stats

`slskd-stats` is a script that parses the `transfers.db` file from a [slskd](https://github.com/slskd/slskd) container and provides detailed statistics about your uploads and downloads, including the ones you've hidden from web UI. The `transfers.db` file is typically located at `/app/data/transfers.db` in the slskd container.

Thanks [Player6734](https://github.com/Player6734/slskd-stats) for the inspiration.

## Features

- Displays total uploaded and downloaded data.
- Shows the number of completed and failed transfers.
- Calculates average upload and download speeds.
- Lists the top users by data transferred.
- Reports common errors encountered during transfers.
- Outputs stats in plain text or JSON format.

## Requirements

- Python 3.6 or higher

## Usage

1. Download the script
2. Get the transfers.db file (typically located at `/app/data/transfers.db` in the slskd container. If you do not have the /app directory mounted, then you can use `docker cp <container_id>:/app/data/transfers.db ./transfers.db` to copy the file directly from the container)
3. Run the script. The script will attempt to open a `./transfers.db` file. You can change the desired file with the `-f path/to/file` flag. (You can also use `-j` to get json instead of plain text and `-r` to get raw info)

## Output example

Default:

```plain
===== slskd-stats =====
= Upload =
Total uploaded: 36.95 GB        (7052 files)
Total failed:   1094
Average speed:  976.97 KB/s
Top users:
  hasko:        2.95 GB
  winivb:       2.77 GB
  psyfarkledon: 1.64 GB
  lolmakermine: 1.31 GB
  MeGUMaNiAC:   998.93 MB

= Download =
Total downloaded:       76.94 GB        (3419 files)
Total failed:   1280
Average speed:  1.93 MB/s
Top users:
  jpegzilla:    8.26 GB
  Antarctiica:  4.11 GB
  +-+:  2.83 GB
  tunnelmaker:  2.50 GB
  iWantToBelieve:       2.43 GB

= Errors =
  Failed to upload file:        732
  Application shut down:        407
  The wait timed out:   233
  The operation was canceled:   218
  Too many files:       196
```

JSON:

```json
{
  "upload": {
    "speed": "976.97 KB/s",
    "completed": 7052,
    "errored": 1094,
    "users": {
      "hasko": "2.95 GB",
      "winivb": "2.77 GB",
      "psyfarkledon": "1.64 GB",
      "lolmakermine": "1.31 GB",
      "MeGUMaNiAC": "998.93 MB"
    },
    "size": "36.95 GB"
  },
  "download": {
    "speed": "1.93 MB/s",
    "completed": 3419,
    "errored": 1280,
    "users": {
      "jpegzilla": "8.26 GB",
      "Antarctiica": "4.11 GB",
      "+-+": "2.83 GB",
      "tunnelmaker": "2.50 GB",
      "iWantToBelieve": "2.43 GB"
    },
    "size": "76.94 GB"
  },
  "errors": {
    "Failed to upload file": 732,
    "Application shut down": 407,
    "The wait timed out": 233,
    "The operation was canceled": 218,
    "Too many files": 196
  }
}
```
