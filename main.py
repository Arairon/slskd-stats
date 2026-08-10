#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from math import floor
from pathlib import Path
from sys import exit, stderr
from urllib.parse import quote

sizeUnits = {
    0: "B",
    1: "KB",
    2: "MB",
    3: "GB",
    4: "TB",
}

stateFlags = [
    "None",
    "Requested",
    "Queued",
    "Initializing",
    "InProgress",
    "Completed",
    "Succeeded",
    "Cancelled",
    "TimedOut",
    "Errored",
    "Rejected",
    "Aborted",
    "Locally",
    "Remotely",
]


def parseState(state: int):
    flags = []
    if state == 0:
        return [stateFlags[0]]
    offset = 0
    while state > 0:
        if state & 1:
            flags.append(stateFlags[offset + 1])
        offset += 1
        state >>= 1
    return flags


def parseOldState(state: str):
    flags = []
    state = state.split(", ")
    for i in stateFlags:
        if i in state:
            flags.append(i)
    return flags


def formatSize(bytes: int):
    units = 0
    while bytes >= 1024:
        units += 1
        bytes /= 1024
    return f"{bytes:.2f} {sizeUnits.get(units, '*2^' + str(units * 10))}"


def isValidTransfersSqliteDB(db: sqlite3.Connection):
    try:
        cur = db.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Transfers' LIMIT 1;"
        )
        return bool(cur.fetchall())
    except sqlite3.DatabaseError:
        return False
    finally:
        cur.close()


def getTransfers(db: sqlite3.Connection):
    cur = db.cursor()
    cur.execute("PRAGMA table_info(Transfers);")
    columns = {row[1] for row in cur.fetchall()}
    # Older schemas may not have Filename; the per-file stats are simply left
    # empty in that case rather than failing the whole run.
    filename = "Filename" if "Filename" in columns else "NULL"
    if filename == "NULL":
        print(
            "warn: no Filename column in this database, per-file stats unavailable",
            file=stderr,
        )
    cur.execute(
        f"SELECT Username, Direction, Size, State, AverageSpeed, Exception, {filename} FROM Transfers;"
    )
    transfers = cur.fetchall()
    cur.close()
    return transfers


@contextmanager
def openTransfersDB(dbFile: Path):
    """Open a transfers.db read-only, even while slskd is running.

    Preferred path is sqlite's read-only URI mode, which can also read a -wal
    it has no write access to (as long as the -shm is readable). If that fails
    -- e.g. no -shm because no writer is attached, or a filesystem sqlite won't
    lock over -- fall back to snapshotting the db + sidecars to a temp dir and
    reading the copy, so the -wal still gets replayed.
    """
    db = None
    reason = None
    try:
        db = sqlite3.connect(f"file:{quote(str(dbFile))}?mode=ro", uri=True)
        db.execute("SELECT count(*) FROM sqlite_master;").fetchone()
    except sqlite3.OperationalError as err:
        # A hot -wal we have no write access to lands here (slskd is running,
        # or the files belong to root); fall through to the snapshot.
        if db is not None:
            db.close()
        db = None
        reason = err
    except sqlite3.DatabaseError:
        pass  # not a database at all, let the caller's validity check say so

    if db is not None:
        try:
            yield db
        finally:
            db.close()
        return

    print(
        f"note: reading a snapshot copy, direct read-only open failed ({reason})",
        file=stderr,
    )
    with tempfile.TemporaryDirectory(prefix="slskd-stats-") as tmp:
        copy = Path(tmp) / "transfers.db"
        shutil.copy2(dbFile, copy)
        for suffix in ("-wal", "-shm"):
            sidecar = dbFile.with_name(dbFile.name + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, copy.with_name(copy.name + suffix))
        db = sqlite3.connect(copy)
        try:
            yield db
        finally:
            db.close()


def splitPath(filename: str):
    """Soulseek paths use backslashes; return (folder, basename, extension)."""
    path = filename.replace("/", "\\")
    folder, _, base = path.rpartition("\\")
    ext = base.rpartition(".")[2].lower() if "." in base else "(none)"
    if len(ext) > 8 or not ext.isalnum():
        ext = "(none)"
    return (folder, base, ext)


def bump(bucket: dict, key: str, size: int):
    entry = bucket.get(key)
    if entry is None:
        entry = bucket[key] = {"count": 0, "bytes": 0}
    entry["count"] += 1
    entry["bytes"] += size


def emptyDirectionStats():
    return {
        "bytes": 0,
        "speed": 0,
        "speedsum": 0.0,
        "completed": 0,
        "errored": 0,
        "uniqueUsers": 0,
        "uniqueFiles": 0,
        "users": {},
        "files": {},
        "folders": {},
        "formats": {},
    }


def calcRawStats(transfers):
    totalStats = {
        "upload": emptyDirectionStats(),
        "download": emptyDirectionStats(),
        "errors": {},
    }

    if len(transfers) == 0:
        return totalStats

    if isinstance(transfers[0][3], str):
        print("warn: You are using an old database format, please update slskd")

    for (
        username,
        direction,
        size,
        state,
        speed,
        error,
        filename,
    ) in transfers:
        if isinstance(state, str):
            state = parseOldState(state)
        else:
            state = parseState(state)
        if "Completed" not in state:
            continue
        succeeded = "Succeeded" in state
        stats = (
            totalStats["upload"] if direction == "Upload" else totalStats["download"]
        )

        if succeeded:
            stats["bytes"] += size
            stats["completed"] += 1
            stats["speedsum"] += speed
            if stats["users"].get(username) is None:
                stats["users"][username] = 0
            stats["users"][username] += size
            if filename:
                folder, _, ext = splitPath(filename)
                bump(stats["files"], filename, size)
                bump(stats["folders"], folder or "(root)", size)
                bump(stats["formats"], ext, size)
        else:
            stats["errored"] += 1
            shortError = " ".join(error.split(" ")[:4]).strip(" .")
            if "appears to" in shortError:
                shortError = "User offline"
            if totalStats["errors"].get(shortError) is None:
                totalStats["errors"][shortError] = 0
            totalStats["errors"][shortError] += 1

    for direction in ("upload", "download"):
        stats = totalStats[direction]
        if stats["speedsum"] and stats["completed"]:
            stats["speed"] = round(stats["speedsum"] / stats["completed"], 2)
        stats["uniqueUsers"] = len(stats["users"])
        stats["uniqueFiles"] = len(stats["files"])
    return totalStats


def topEntries(bucket: dict, top: int, key="count"):
    """Sort a {name: {count, bytes}} bucket, returning a list of pretty rows."""
    ranked = sorted(
        bucket.items(), key=lambda i: (i[1][key], i[1]["bytes"]), reverse=True
    )[:top]
    return [
        {"name": name, "count": v["count"], "size": formatSize(v["bytes"])}
        for name, v in ranked
    ]


def prettifyStatsDirection(stats, top=5):
    stats["size"] = formatSize(stats["bytes"])
    del stats["bytes"]
    stats["speed"] = formatSize(floor(stats["speed"])) + "/s"
    del stats["speedsum"]
    usertop = sorted(stats["users"].items(), key=lambda i: i[1], reverse=True)[:top]
    stats["users"] = {k: formatSize(v) for k, v in usertop}
    stats["files"] = topEntries(stats["files"], top)
    stats["folders"] = topEntries(stats["folders"], top)
    stats["formats"] = topEntries(stats["formats"], top, key="bytes")
    return stats


def prettifyStats(stats, top=5):
    stats["upload"] = prettifyStatsDirection(stats["upload"], top)
    stats["download"] = prettifyStatsDirection(stats["download"], top)
    errortop = sorted(stats["errors"].items(), key=lambda i: i[1], reverse=True)[:top]
    stats["errors"] = dict(errortop)
    return stats


def elide(text: str, width: int):
    """Trim from the left; the tail of a path is the informative half."""
    if width <= 1 or len(text) <= width:
        return text
    return "..." + text[-(width - 3) :]


def shortenFilePath(path: str):
    """Keep the last two path components, e.g. 'Album\\01 - Track.flac'."""
    parts = path.replace("/", "\\").split("\\")
    return "\\".join(parts[-2:])


def printRanked(rows, empty: str, width: int):
    if not rows:
        print(f"  {empty}")
        return
    countWidth = max(len(str(row["count"])) for row in rows)
    sizeWidth = max(len(row["size"]) for row in rows)
    nameWidth = max(24, width - (countWidth + sizeWidth + 9))
    for row in rows:
        name = elide(row["name"], nameWidth)
        print(f"  {row['count']:>{countWidth}} x {row['size']:>{sizeWidth}}  {name}")


def printDirection(stats, direction: str, width: int):
    isUpload = direction == "upload"
    print(f"= {'Upload' if isUpload else 'Download'} =")
    print(
        f"Total {'uploaded' if isUpload else 'downloaded'}:\t{stats['size']}"
        f"\t({stats['completed']} files)"
    )
    print(f"Total failed:\t{stats['errored']}")
    print(f"Average speed:\t{stats['speed']}")
    print(f"Unique files:\t{stats['uniqueFiles']}")
    print(f"Unique users:\t{stats['uniqueUsers']}")
    print("Top users:")
    longestNameLength = len(max(stats["users"].keys(), key=len)) if stats["users"] else 0
    for user, size in stats["users"].items():
        print(f"  {user}:{' ' * (longestNameLength - len(user))} \t {size}")
    if len(stats["users"]) == 0:
        print(
            "  No one has downloaded anything from you yet"
            if isUpload
            else "  You haven't downloaded from anyone yet"
        )
    print("Top files:")
    files = [dict(row, name=shortenFilePath(row["name"])) for row in stats["files"]]
    printRanked(files, "No files yet", width)
    print("Top folders:")
    printRanked(stats["folders"], "No folders yet", width)
    print("Top formats:")
    printRanked(stats["formats"], "No formats yet", width)


def prettyPrint(stats, top=5):
    stats = prettifyStats(stats, top)
    width = shutil.get_terminal_size((100, 24)).columns
    print("===== slskd-stats =====")
    printDirection(stats["upload"], "upload", width)
    print()
    printDirection(stats["download"], "download", width)
    print("\n= Errors =")
    for error, count in stats["errors"].items():
        print(f'  "{error}":\t{count}')
    if len(stats["errors"]) == 0:
        print("  No errors")


def main():
    parser = argparse.ArgumentParser(
        prog="slskd-stats", description="Arai's slskd stats calculator"
    )
    parser.add_argument(
        "-f", "--file", help="Name of the file to process", default="./transfers.db"
    )
    parser.add_argument(
        "-j", "--json", action="store_true", help="Outputs json instead of plain text"
    )
    parser.add_argument(
        "-r",
        "--rawjson",
        action="store_true",
        help="Outputs raw stats in json. Requires -j flag",
    )
    parser.add_argument(
        "-n",
        "--top",
        type=int,
        default=5,
        help="How many entries to show in each top list (default: 5)",
    )
    args = parser.parse_args()

    dbFile = Path(args.file)
    if not dbFile.exists() or not dbFile.is_file():
        print(f"Target: {dbFile.resolve()} is not a valid file")
        exit(1)

    with openTransfersDB(dbFile.resolve()) as db:
        if not isValidTransfersSqliteDB(db):
            print(
                f"File: {dbFile.resolve()} is either not a valid sqlite3 database or does not contain the 'Transfers' table."
            )
            exit(1)
        transfers = getTransfers(db)

    stats = calcRawStats(transfers)
    if args.json:
        if not args.rawjson:
            stats = prettifyStats(stats, args.top)
        print(json.dumps(stats, indent=2))
        exit(0)

    prettyPrint(stats, args.top)


if __name__ == "__main__":
    main()
