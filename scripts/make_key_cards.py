#!/usr/bin/env python3
"""Generate print-ready key cards (PDF) from keys/keys.csv (PLAN.md Phase 4).

One card per team: team ID, API key (text + QR), endpoint URL, budgets, and a QR
to the docs page. 4 cards per US-Letter page, cut lines included.

Usage:
    python scripts/make_key_cards.py                # keys/keys.csv -> keys/key_cards.pdf
    python scripts/make_key_cards.py --dry-run

Requires: pip install qrcode reportlab
"""

import argparse
import csv
import sys
from pathlib import Path

DOCS_URL = "https://ohack.dev/hack/2026_fall/ai"
ENDPOINT = "https://ai.ohack.dev/v1"

CARD_W, CARD_H = 4.25 * 72, 5.5 * 72  # quarter of US Letter, in points


def make_qr_image(data: str):
    import qrcode
    from reportlab.lib.utils import ImageReader

    qr = qrcode.QRCode(border=1, box_size=8)
    qr.add_data(data)
    qr.make(fit=True)
    return ImageReader(qr.make_image(fill_color="black", back_color="white").get_image())


def draw_key_block(c, pad, top, label, key):
    """Key as split text + QR to its right. Returns the y below the block."""
    from reportlab.lib.units import inch

    qr_size = 0.95 * inch
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(pad, top, label)
    c.setFont("Courier", 6.8)
    mid = (len(key) + 1) // 2
    c.drawString(pad, top - 13, key[:mid])
    c.drawString(pad, top - 23, key[mid:])
    c.drawImage(make_qr_image(key), CARD_W - pad - qr_size, top - 23 - qr_size + 18,
                qr_size, qr_size)
    return top - 23 - qr_size + 10


def draw_card(c, x, y, row):
    from reportlab.lib.units import inch

    pad = 0.25 * inch
    c.saveState()
    c.translate(x, y)
    c.setLineWidth(0.5)
    c.setDash(2, 2)
    c.rect(0, 0, CARD_W, CARD_H)  # cut line
    c.setDash()

    c.setFont("Helvetica-Bold", 15)
    c.drawString(pad, CARD_H - pad - 4, f"OHack AI — {row['team_id']}")
    c.setFont("Helvetica", 8.5)
    c.drawString(pad, CARD_H - pad - 18, "Fall 2026 · one gateway, every coding tool")

    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(pad, CARD_H - pad - 38, "Endpoint")
    c.setFont("Courier", 9.5)
    c.drawString(pad + 0.75 * inch, CARD_H - pad - 38, ENDPOINT)

    q_main = row.get("quota_main") or "15"
    q_front = row.get("quota_frontier") or "20"
    next_y = draw_key_block(
        c, pad, CARD_H - pad - 62,
        f"Key 1 — models ohack / ohack-free (${q_main} budget)", row["key"])
    if row.get("frontier_key"):
        next_y = draw_key_block(
            c, pad, next_y - 14,
            f"Key 2 — model ohack-frontier (${q_front} budget)", row["frontier_key"])

    qr_size = 0.85 * inch
    c.drawImage(make_qr_image(DOCS_URL), pad, 0.55 * inch, qr_size, qr_size)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(pad + qr_size + 0.15 * inch, 1.12 * inch, "Setup guide (2 min):")
    c.setFont("Helvetica", 8.5)
    c.drawString(pad + qr_size + 0.15 * inch, 0.97 * inch, DOCS_URL)
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(pad + qr_size + 0.15 * inch, 0.80 * inch, "Keys are per-team. Keep them")
    c.drawString(pad + qr_size + 0.15 * inch, 0.69 * inch, "out of git and public demos.")
    c.setFont("Helvetica", 7.5)
    c.drawString(pad, 0.32 * inch, "Budget gone or key leaked? Find an organizer.")
    c.restoreState()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default="keys/keys.csv")
    ap.add_argument("--out", default="keys/key_cards.pdf")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"error: {csv_path} not found (run provision_keys.py first)", file=sys.stderr)
        return 2
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows)} keys in {csv_path}")
    if args.dry_run:
        for r in rows:
            print(f"  card: {r['team_id']} key={r['key'][:12]}…")
        print("Dry run: no PDF written.")
        return 0

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(args.out, pagesize=letter)
    positions = [(0, CARD_H), (CARD_W, CARD_H), (0, 0), (CARD_W, 0)]
    for i, row in enumerate(rows):
        draw_card(c, *positions[i % 4], row)
        if i % 4 == 3:
            c.showPage()
    if len(rows) % 4:
        c.showPage()
    c.save()
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
