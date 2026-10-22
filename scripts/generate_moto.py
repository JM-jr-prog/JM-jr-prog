#!/usr/bin/env python3
"""Animated SVG: a motorcycle riding across your GitHub contribution graph.

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
TEXT = "#e8d9bf"
ORANGE = "#ff8a3d"

# Ride timing
SPEED = 280   # px per second along a row
TURN = 0.35   # seconds for the U-turn between rows
PARK = 1.2    # pause at the end before the loop restarts

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


def wheel(cx):
    return f"""
  <g transform="translate({cx},-5)">
    <g>
      <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="0.35s" repeatCount="indefinite"/>
      <circle r="5" fill="{BG}" stroke="{TEXT}" stroke-width="1.6"/>
      <line x1="-5" y1="0" x2="5" y2="0" stroke="{ORANGE}" stroke-width="1"/>
      <line x1="0" y1="-5" x2="0" y2="5" stroke="{ORANGE}" stroke-width="1"/>
    </g>
  </g>"""


def bike_art():
    return f"""
  <polygon points="12,-12 36,-18 36,-5" fill="#ffd9a0" opacity="0.25"/>
  {wheel(-9)}
  {wheel(9)}
  <path d="M-9,-5 L-3,-10 L6,-10 L9,-5" fill="none" stroke="#d35400" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M9,-5 L6,-15" stroke="{TEXT}" stroke-width="1.6" stroke-linecap="round"/>
  <line x1="4" y1="-16" x2="8" y2="-15.5" stroke="{TEXT}" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M-6,-11 Q-1,-17 5,-13 L4,-9.5 L-4,-9.5 Z" fill="{ORANGE}"/>
  <rect x="-11" y="-12.5" width="7" height="2.6" rx="1.2" fill="{TEXT}"/>
  <line x1="-6" y1="-13" x2="-1.5" y2="-21" stroke="#b34700" stroke-width="2.6" stroke-linecap="round"/>
  <line x1="-2.5" y1="-19" x2="5.5" y2="-15.8" stroke="#b34700" stroke-width="1.8" stroke-linecap="round"/>
  <circle cx="-0.5" cy="-24" r="3.2" fill="{ORANGE}" stroke="{BG}" stroke-width="0.8"/>
  <rect x="0.8" y="-25" width="2.6" height="1.6" rx="0.6" fill="{BG}"/>"""


def build_svg(grid, total):
    weeks = len(grid)
    width = PAD_X * 2 + weeks * PITCH - GAP
    height = PAD_TOP + 7 * PITCH - GAP + 24
    x_left = PAD_X
    x_right = PAD_X + weeks * PITCH - GAP

    # ---- ride timeline: serpentine, left->right, U-turn, right->left, ... ----
    segs = []  # (t0, t1, x0, y0, x1, y1, facing_right)
    row_info = {}
    t = 0.0
    last_x = x_left
    last_y = PAD_TOP + CELL
    last_dir = True
    for r in range(7):
        y = PAD_TOP + r * PITCH + CELL
        right = r % 2 == 0
        xa, xb = (x_left, x_right) if right else (x_right, x_left)
        dur = abs(xb - xa) / SPEED
        row_info[r] = (t, xa)
        segs.append((t, t + dur, xa, y, xb, y, right))
        t += dur
        last_x, last_y, last_dir = xb, y, right
        if r < 6:
            segs.append((t, t + TURN, xb, y, xb, y + PITCH, not right))
            t += TURN
            last_y = y + PITCH
    segs.append((t, t + PARK, last_x, last_y, last_x, last_y, last_dir))
    T = t + PARK

    move_times = [f"{s[0] / T:.5f}" for s in segs] + ["1"]
    move_vals = [f"{s[2]:.1f} {s[3]:.1f}" for s in segs] + [f"{segs[-1][4]:.1f} {segs[-1][5]:.1f}"]
    flip_times = [f"{s[0] / T:.5f}" for s in segs]
    flip_vals = ["1 1" if s[6] else "-1 1" for s in segs]

    # ---- tiles + the glow trail the bike leaves ----
    tiles, glows = [], []
    for w, col in enumerate(grid):
        for d, lvl in enumerate(col):
            if lvl is None:
                continue
            x = PAD_X + w * PITCH
            y = PAD_TOP + d * PITCH
            tiles.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{COLORS[lvl]}"/>')
            t_row, xa = row_info[d]
            t_pass = t_row + abs((x + CELL / 2) - xa) / SPEED
            delay = -(T - t_pass)
            glows.append(
                f'<rect class="f" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'style="animation-delay:{delay:.2f}s"/>'
            )

    start_x, start_y = segs[0][2], segs[0][3]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Motorcycle riding across the GitHub contribution graph">
<style>
  .f {{ fill: #fff1d9; opacity: 0; animation: flash {T:.2f}s linear infinite; }}
  @keyframes flash {{ 0% {{ opacity: .9; }} 7% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
  text {{ font-family: 'Fira Code', ui-monospace, Menlo, Consolas, monospace; }}
</style>
<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>
<text x="{PAD_X}" y="27" font-size="13" font-weight="700" fill="{ORANGE}">&gt; ride --contributions</text>
<text x="{width - PAD_X}" y="27" font-size="12" fill="{TEXT}" text-anchor="end">{total} in the last year</text>
{chr(10).join(tiles)}
{chr(10).join(glows)}
<g transform="translate({start_x:.1f},{start_y:.1f})">
  <animateTransform attributeName="transform" type="translate" calcMode="linear" dur="{T:.2f}s" repeatCount="indefinite"
    keyTimes="{';'.join(move_times)}" values="{';'.join(move_vals)}"/>
  <g>
    <animateTransform attributeName="transform" type="scale" calcMode="discrete" dur="{T:.2f}s" repeatCount="indefinite"
      keyTimes="{';'.join(flip_times)}" values="{';'.join(flip_vals)}"/>
    <g transform="scale(0.72)">{bike_art()}
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
