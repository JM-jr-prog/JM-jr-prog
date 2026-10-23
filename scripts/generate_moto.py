#!/usr/bin/env python3
"""Animated SVG: a top-down motorcycle riding over your GitHub contribution tiles
and collecting every tile that has contributions.

Usage:
  GITHUB_TOKEN=... GH_USER=JM-jr-prog python scripts/generate_moto.py
  python scripts/generate_moto.py --demo        # fake data, no token needed
"""
import json
import os
import random
import sys
import urllib.request

USER = os.environ.get("GH_USER", "JM-jr-prog")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "assets/moto-contrib.svg")

# Layout
CELL, GAP = 12, 4
PITCH = CELL + GAP
PAD_X, PAD_TOP = 24, 44

# Theme (matches the black + purple + orange profile)
BG = "#0d0b10"
COLORS = ["#1a1424", "#3d2a5c", "#6b3fa0", "#c2531f", "#ff8a3d"]
EMPTY = COLORS[0]
FLASH = "#fff1d9"
TEXT = "#e8d9bf"
ORANGE = "#ff8a3d"

# Ride timing
SPEED = 240   # px per second along a row
TURN = 0.55   # seconds for the U-turn between rows
PARK = 2.4    # pause at the end (tiles regrow here) before the loop restarts
OVERSHOOT = 16  # how far the bike rides past the first/last tile before turning

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def fetch_grid():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionLevel weekday } }
          }
        }
      }
    }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "moto-contrib",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    grid = []
    for week in cal["weeks"]:
        col = [None] * 7
        for day in week["contributionDays"]:
            col[day["weekday"]] = LEVELS[day["contributionLevel"]]
        grid.append(col)
    return grid, cal["totalContributions"]


def demo_grid():
    random.seed(7)
    grid = [[random.choices([0, 1, 2, 3, 4], [5, 3, 2, 1, 1])[0] for _ in range(7)] for _ in range(53)]
    return grid, 321


def bike_art():
    """Top-down motorcycle, centered on (0,0), facing right (+x)."""
    return f"""
    <polygon points="12,0 32,-10 32,10" fill="#ffd9a0" opacity="0.2"/>
    <rect x="-13" y="-2.3" width="6.5" height="4.6" rx="2.2" fill="#2a2036" stroke="{TEXT}" stroke-width="1"/>
    <rect x="6.5" y="-1.9" width="6" height="3.8" rx="1.9" fill="#2a2036" stroke="{TEXT}" stroke-width="1"/>
    <rect x="-8" y="-1.3" width="16" height="2.6" rx="1.3" fill="#d35400"/>
    <ellipse cx="1.8" cy="0" rx="5.2" ry="3.3" fill="{ORANGE}"/>
    <ellipse cx="-5.2" cy="0" rx="3.4" ry="2.7" fill="{TEXT}"/>
    <line x1="5.6" y1="-5.8" x2="5.6" y2="5.8" stroke="{TEXT}" stroke-width="1.7" stroke-linecap="round"/>
    <line x1="-1.5" y1="-3.6" x2="5.4" y2="-5.2" stroke="#b34700" stroke-width="2" stroke-linecap="round"/>
    <line x1="-1.5" y1="3.6" x2="5.4" y2="5.2" stroke="#b34700" stroke-width="2" stroke-linecap="round"/>
    <ellipse cx="-2.6" cy="0" rx="2.7" ry="4.4" fill="#b34700"/>
    <circle cx="-0.6" cy="0" r="3.1" fill="{ORANGE}" stroke="{BG}" stroke-width="0.8"/>
    <rect x="0.7" y="-1.7" width="2.1" height="3.4" rx="0.9" fill="{BG}"/>
    <circle cx="-13.8" cy="0" r="1.2" fill="#ff3b30"/>"""


def build_svg(grid, total):
    weeks = len(grid)
    width = PAD_X * 2 + weeks * PITCH - GAP
    height = PAD_TOP + 7 * PITCH - GAP + 24
    x_left = PAD_X + CELL / 2 - OVERSHOOT
    x_right = PAD_X + (weeks - 1) * PITCH + CELL / 2 + OVERSHOOT

    # ---- ride timeline: serpentine rows, bike centered on each tile row ----
    # seg = (t0, t1, x0, y0, x1, y1, angle0, angle1); angle 0 = facing right, 180 = left
    segs = []
    row_info = {}
    t = 0.0
    for r in range(7):
        y = PAD_TOP + r * PITCH + CELL / 2
        right = r % 2 == 0
        xa, xb = (x_left, x_right) if right else (x_right, x_left)
        a = 0 if right else 180
        dur = abs(xb - xa) / SPEED
        row_info[r] = (t, xa)
        segs.append((t, t + dur, xa, y, xb, y, a, a))
        t += dur
        if r < 6:
            # U-turn: drive down one row while rotating through "facing down" (90 deg)
            segs.append((t, t + TURN, xb, y, xb, y + PITCH, a, 180 - a))
            t += TURN
    ride_end = t
    segs.append((t, t + PARK, xb, y, xb, y, a, a))
    T = ride_end + PARK

    move_times = [f"{s[0] / T:.5f}" for s in segs] + ["1"]
    move_vals = [f"{s[2]:.1f} {s[3]:.1f}" for s in segs] + [f"{segs[-1][4]:.1f} {segs[-1][5]:.1f}"]
    rot_vals = [str(s[6]) for s in segs] + [str(segs[-1][7])]

    # ---- tiles: contribution tiles flash and get "collected" when the bike rides over ----
    d1 = 0.02 / T                      # flash on contact
    fade = 0.5 / T                     # flash -> collected (empty)
    regrow_a = (ride_end + 0.5) / T    # tiles regrow while the bike is parked
    regrow_b = (ride_end + 1.7) / T
    tiles = []
    for w, col in enumerate(grid):
        for d, lvl in enumerate(col):
            if lvl is None:
                continue
            x = PAD_X + w * PITCH
            y = PAD_TOP + d * PITCH
            base = COLORS[lvl]
            head = f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{base}"'
            if lvl == 0:
                tiles.append(head + "/>")
                continue
            t_row, xa = row_info[d]
            p = (t_row + abs((x + CELL / 2) - xa) / SPEED) / T
            keys = [0, p, p + d1, p + fade, regrow_a, regrow_b, 1]
            vals = [base, base, FLASH, EMPTY, EMPTY, base, base]
            tiles.append(
                head + f'><animate attributeName="fill" dur="{T:.2f}s" repeatCount="indefinite" '
                f'keyTimes="{";".join(f"{k:.5f}" for k in keys)}" values="{";".join(vals)}"/></rect>'
            )

    start_x, start_y = segs[0][2], segs[0][3]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Top-down motorcycle collecting the GitHub contribution tiles">
<style>text {{ font-family: 'Fira Code', ui-monospace, Menlo, Consolas, monospace; }}</style>
<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>
<text x="{PAD_X}" y="27" font-size="13" font-weight="700" fill="{ORANGE}">&gt; ride --contributions</text>
<text x="{width - PAD_X}" y="27" font-size="12" fill="{TEXT}" text-anchor="end">{total} in the last year</text>
{chr(10).join(tiles)}
<g transform="translate({start_x:.1f},{start_y:.1f})">
  <animateTransform attributeName="transform" type="translate" calcMode="linear" dur="{T:.2f}s" repeatCount="indefinite"
    keyTimes="{';'.join(move_times)}" values="{';'.join(move_vals)}"/>
  <g>
    <animateTransform attributeName="transform" type="rotate" calcMode="linear" dur="{T:.2f}s" repeatCount="indefinite"
      keyTimes="{';'.join(move_times)}" values="{';'.join(rot_vals)}"/>
    <g transform="scale(0.9)">{bike_art()}
    </g>
  </g>
</g>
</svg>
"""


def main():
    demo = "--demo" in sys.argv
    if demo:
        grid, total = demo_grid()
    else:
        if not TOKEN:
            sys.exit("GITHUB_TOKEN is not set. Use --demo to preview with fake data.")
        grid, total = fetch_grid()
    svg = build_svg(grid, total)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {OUT} ({len(svg) // 1024} KB, {len(grid)} weeks)")


if __name__ == "__main__":
    main()
