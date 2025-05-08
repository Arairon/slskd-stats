#!/usr/bin/env python3
import sqlite3
import argparse
from sys import exit
from pathlib import Path
import json
from math import floor

sizeUnits = {
    0: "B",
    1: "KB",
    2: "MB",
    3: "GB",
    4: "TB",
}


def formatSize(bytes: int):
    units = 0
    while bytes >= 1024:
        units += 1
        bytes /= 1024
    return f"{bytes:.2f} {sizeUnits.get(units, '*2^' + str(units*10))}"


def isValidTransfersSqliteDB(db: sqlite3.Connection):
    try:
        cur = db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Transfers' LIMIT 1;")
        return bool(cur.fetchall())
    except sqlite3.DatabaseError:
        return False
    finally:
        cur.close()


def getTransfers(db: sqlite3.Connection):
    cur = db.cursor()
    cur.execute("SELECT Username, Direction, Size, State, AverageSpeed, Exception FROM Transfers;")
    transfers = cur.fetchall()
    cur.close()
    return transfers


def calcRawStats(transfers):
    totalStats = {
        "upload": {
            "bytes": 0,
            "speed": -1,
            "speedsum": 0.0,
            "completed": 0,
            "errored": 0,
            "users": {},
        },
        "download": {
            "bytes": 0,
            "speed": -1,
            "speedsum": 0.0,
            "completed": 0,
            "errored": 0,
            "users": {},
        },
        "errors": {},
    }
    for (
        username,
        direction,
        size,
        state,
        speed,
        error,
    ) in transfers:
        state = state.split(", ")
        if state[0] != "Completed":
            continue
        completed = state[1] == "Succeeded"
        stats = totalStats["upload"] if direction == "Upload" else totalStats["download"]

        if completed:
            stats["bytes"] += size
            stats["completed"] += 1
            stats["speedsum"] += speed
            if stats["users"].get(username) is None:
                stats["users"][username] = 0
            stats["users"][username] += size
        else:
            stats["errored"] += 1
            shortError = " ".join(error.split(" ")[:4]).strip(" .")
            if "appears to" in shortError:
                shortError = "User offline"
            if totalStats["errors"].get(shortError) is None:
                totalStats["errors"][shortError] = 0
            totalStats["errors"][shortError] += 1
    totalStats["upload"]["speed"] = round(totalStats["upload"]["speedsum"] / totalStats["upload"]["completed"], 2)
    totalStats["download"]["speed"] = round(totalStats["download"]["speedsum"] / totalStats["download"]["completed"], 2)
    return totalStats


def prettifyStatsDirection(stats):
    stats["size"] = formatSize(stats["bytes"])
    del stats["bytes"]
    stats["speed"] = formatSize(floor(stats["speed"])) + "/s"
    del stats["speedsum"]
    usertop = sorted(stats["users"].items(), key=lambda i: i[1], reverse=True)[:5]
    stats["users"] = {k: formatSize(v) for k, v in usertop}
    return stats


def prettifyStats(stats):
    stats["upload"] = prettifyStatsDirection(stats["upload"])
    stats["download"] = prettifyStatsDirection(stats["download"])
    errortop = sorted(stats["errors"].items(), key=lambda i: i[1], reverse=True)[:5]
    stats["errors"] = dict(errortop)
    return stats


def prettyPrint(stats):
    stats = prettifyStats(stats)
    print("===== slskd-stats =====")
    print("= Upload =")
    print(f"Total uploaded:\t{stats['upload']['size']}\t({stats['upload']['completed']} files)")
    print(f"Total failed:\t{stats['upload']['errored']}")
    print(f"Average speed:\t{stats['upload']['speed']}")
    print("Top users:")
    for user, size in stats["upload"]["users"].items():
        print(f"  {user}:\t{size}")
    if len(stats["download"]["users"]) == 0:
        print("No one has downloaded anything from you yet")
    print("\n= Download =")
    print(f"Total downloaded:\t{stats['download']['size']}\t({stats['download']['completed']} files)")
    print(f"Total failed:\t{stats['download']['errored']}")
    print(f"Average speed:\t{stats['download']['speed']}")
    print("Top users:")
    for user, size in stats["download"]["users"].items():
        print(f"  {user}:\t{size}")
    if len(stats["download"]["users"]) == 0:
        print("You haven't downloaded from anyone yet")
    print("\n= Errors =")
    for error, count in stats["errors"].items():
        print(f"  {error}:\t{count}")
    if len(stats["errors"]) == 0:
        print("  No errors")


def main():
    parser = argparse.ArgumentParser(prog="slskd-stats", description="Arai's slskd stats calculator")
    parser.add_argument("-f", "--file", help="Name of the file to process", default="./transfers.db")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-j", "--json", action="store_true", help="Outputs json instead of plain text")
    parser.add_argument(
        "-r",
        "--rawjson",
        action="store_true",
        help="Outputs raw stats in json. Requires -j flag",
    )
    parser.add_argument(
        "-i",
        "--indentjson",
        action="store_true",
        help="Adds indentation to json output. Requires -j flag",
    )
    args = parser.parse_args()

    dbFile = Path(args.file)
    if not dbFile.exists() or not dbFile.is_file():
        print(f"Target: {dbFile.resolve()} is not a valid file")
        exit(1)
    db = sqlite3.connect(dbFile.resolve())
    if not isValidTransfersSqliteDB(db):
        print(
            f"File: {dbFile.resolve()} is either not a valid sqlite3 database or does not contain the 'Transfers' table."
        )
        exit(1)

    transfers = getTransfers(db)
    stats = calcRawStats(transfers)
    if args.json:
        if not args.rawjson:
            stats = prettifyStats(stats)
        print(json.dumps(stats, indent=(2 if args.indentjson else 0)))
        exit(0)

    prettyPrint(stats)


if __name__ == "__main__":
    main()
