import json, os, subprocess, sys, datetime as dt

W, H = 1000, 280
PADL, PADR, PADT, PADB = 52, 24, 40, 46

def fetch(login):
    q = ('query($login:String!){user(login:$login){contributionsCollection'
         '{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}')
    out = subprocess.check_output(
        ["gh", "api", "graphql", "-f", f"query={q}", "-F", f"login={login}"])
    cal = json.loads(out)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    return days, cal["totalContributions"]

def path_for(days, maxv):
    n = len(days)
    sx = (W - PADL - PADR) / max(n - 1, 1)
    sy = (H - PADT - PADB)
    pts = []
    for i, d in enumerate(days):
        x = PADL + i * sx
        y = PADT + sy - (d["contributionCount"] / maxv) * sy
        pts.append((x, y))
    # Catmull-Rom -> cubic bezier for a smooth line
    seg = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        # clamp control points into the plot band: spiky data makes
        # Catmull-Rom overshoot below zero and into the month labels
        cy = lambda v: min(max(v, PADT), PADT + sy)
        cx = lambda v: min(max(v, PADL), W - PADR)
        c1 = (cx(p1[0] + (p2[0] - p0[0]) / 6), cy(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (cx(p2[0] - (p3[0] - p1[0]) / 6), cy(p2[1] - (p3[1] - p1[1]) / 6))
        seg.append(f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    line = " ".join(seg)
    base = PADT + sy
    area = f"{line} L {pts[-1][0]:.1f} {base:.1f} L {pts[0][0]:.1f} {base:.1f} Z"
    return line, area, pts, sx

def month_ticks(days, sx):
    out, seen = [], None
    for i, d in enumerate(days):
        m = d["date"][:7]
        if m != seen:
            seen = m
            lbl = dt.date.fromisoformat(d["date"]).strftime("%b")
            out.append((PADL + i * sx, lbl))
    return out[1:] if len(out) > 12 else out

def render(days, total, theme):
    c = dict(
        light=dict(bg="#F9F7F4", grid="#E4E1DB", text="#5A6E75", head="#1B3139",
                   line="#FF3621", a1="#FF3621", a2="#FF3621", dot="#FF5F46", sub="#8A9AA1"),
        dark=dict(bg="#1B3139", grid="#2C4A54", text="#9FB2B9", head="#F9F7F4",
                  line="#FF3621", a1="#FF5F46", a2="#FF3621", dot="#FF9E8E", sub="#7B9099"),
    )[theme]
    maxv = max(max(d["contributionCount"] for d in days), 1)
    line, area, pts, sx = path_for(days, maxv)
    sy = H - PADT - PADB
    grid = "".join(
        f'<line x1="{PADL}" y1="{PADT + sy * f:.1f}" x2="{W - PADR}" y2="{PADT + sy * f:.1f}" '
        f'stroke="{c["grid"]}" stroke-width="1" stroke-dasharray="3 4"/>'
        f'<text x="{PADL - 10}" y="{PADT + sy * f + 4:.1f}" text-anchor="end" '
        f'fill="{c["text"]}" font-size="11">{round(maxv * (1 - f))}</text>'
        for f in (0, 0.25, 0.5, 0.75, 1))
    months = "".join(
        f'<text x="{x:.1f}" y="{H - PADB + 22:.1f}" text-anchor="middle" '
        f'fill="{c["text"]}" font-size="11">{l}</text>' for x, l in month_ticks(days, sx))
    peak = max(pts, key=lambda p: -p[1])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI,Helvetica,Arial,sans-serif">
<defs><linearGradient id="a" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="{c['a1']}" stop-opacity="0.38"/>
<stop offset="100%" stop-color="{c['a2']}" stop-opacity="0.02"/></linearGradient></defs>
<rect width="{W}" height="{H}" rx="10" fill="{c['bg']}"/>
<text x="{PADL - 10}" y="24" fill="{c['head']}" font-size="15" font-weight="700">Contribution Activity</text>
<text x="{W - PADR}" y="24" text-anchor="end" fill="{c['line']}" font-size="15" font-weight="700">{total:,}</text>
<text x="{W - PADR}" y="24" text-anchor="end" fill="{c['sub']}" font-size="11" dy="14">contributions &#183; past year</text>
{grid}
<path d="{area}" fill="url(#a)"/>
<path d="{line}" fill="none" stroke="{c['line']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="{peak[0]:.1f}" cy="{peak[1]:.1f}" r="4" fill="{c['dot']}" stroke="{c['bg']}" stroke-width="2"/>
{months}
</svg>'''

login = sys.argv[1]
outdir = sys.argv[2]
days, total = fetch(login)
os.makedirs(outdir, exist_ok=True)
for theme, name in (("light", "activity-graph.svg"), ("dark", "activity-graph-dark.svg")):
    open(os.path.join(outdir, name), "w").write(render(days, total, theme))
    print("wrote", name)
