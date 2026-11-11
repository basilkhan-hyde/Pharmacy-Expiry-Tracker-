#!/usr/bin/env python3
"""
Pharmacy Inventory & Expiry Tracker (Interactive Shell Version)
-------------------------------------------------------------
Tracks medicine stock, batch numbers, prices, and expiry dates 
directly in the terminal using Python's built-in `cmd` module.
Data is saved to inventory.json in the same folder.

Run: python pharmacy_tracker.py
"""

import cmd
import json
import math
import os
import random
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_FILE = Path(__file__).resolve().parent / "inventory.json"
LOW_STOCK_LIMIT = 10
EXPIRY_WARN_DAYS = 30

SAMPLE_MEDICINES = (
    ("Paracetamol 500 mg", 0.08), ("Ibuprofen 400 mg", 0.12),
    ("Amoxicillin 500 mg", 0.35), ("Cetirizine 10 mg", 0.15),
    ("Omeprazole 20 mg", 0.22), ("Metformin 500 mg", 0.10),
    ("Atorvastatin 20 mg", 0.30), ("Amlodipine 5 mg", 0.18),
    ("Loratadine 10 mg", 0.14), ("Azithromycin 250 mg", 0.90),
    ("Aspirin 75 mg", 0.05), ("Vitamin C 500 mg", 0.06),
    ("Multivitamin Tablets", 0.20), ("Oral Rehydration Salts", 0.75),
    ("Cough Syrup 100 ml", 3.20), ("Antiseptic Solution 100 ml", 2.40),
    ("Diclofenac Gel 30 g", 3.80), ("Salbutamol Inhaler", 4.50),
)


# --------------------------------------------------------------------------- #
# Core Logic & Helpers
# --------------------------------------------------------------------------- #
def parse_date(text):
    text = text.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def expiry_state(item, today):
    exp = parse_date(str(item.get("expiry", "")))
    if exp is None:
        return "invalid", None
    days = (exp - today).days
    if days < 0:
        return "expired", days
    if days <= EXPIRY_WARN_DAYS:
        return "soon", days
    return "ok", days


def is_low(item):
    return item["qty"] < LOW_STOCK_LIMIT


def status_text(item, today):
    state, days = expiry_state(item, today)
    if state == "expired":
        text = f"EXPIRED ({-days}d ago)"
    elif state == "soon":
        text = "EXPIRES TODAY" if days == 0 else f"Expiring ({days}d)"
    elif state == "invalid":
        text = "Invalid date"
    else:
        text = "OK"
    
    if is_low(item):
        text += " | LOW STOCK"
    return text


def normalise(record):
    if not isinstance(record, dict):
        return None
    try:
        return {
            "id": str(record["id"]),
            "name": str(record.get("name", "")),
            "batch": str(record.get("batch", "")),
            "qty": int(record.get("qty", 0)),
            "price": float(record.get("price", 0)),
            "expiry": str(record.get("expiry", "")),
        }
    except (KeyError, TypeError, ValueError):
        return None


def make_sample_records(entries, today=None):
    today = today or date.today()
    n = len(entries)
    if n == 0: return []
    
    buckets = ["expired"] * max(2, n // 6) + ["soon"] * max(2, n // 5)
    buckets += ["ok"] * max(0, n - len(buckets))
    random.shuffle(buckets)
    low_idx = set(random.sample(range(n), min(3, n)))

    records = []
    for i, (name, price) in enumerate(entries):
        bucket = buckets[i]
        if bucket == "expired":
            days = -random.randint(3, 240)
        elif bucket == "soon":
            days = random.randint(0, EXPIRY_WARN_DAYS)
        else:
            days = random.randint(EXPIRY_WARN_DAYS + 1, 900)
            
        qty = random.randint(0, LOW_STOCK_LIMIT - 1) if i in low_idx else random.randint(20, 250)
        records.append({
            "name": name, "batch": f"{random.choice('ABCDEFGHJK')}{random.randint(1000, 9999)}",
            "qty": qty, "price": price, "expiry": (today + timedelta(days=days)).isoformat(),
        })
    return records


# --------------------------------------------------------------------------- #
# CLI Shell Application
# --------------------------------------------------------------------------- #
class PharmacyShell(cmd.Cmd):
    intro = "\n" + "="*80 + "\n   PHARMACY INVENTORY TRACKER SHELL   \n" + "="*80 + "\nType 'help' or '?' to list commands. Type 'exit' to quit.\n"
    prompt = "pharmacy> "

    def __init__(self):
        super().__init__()
        self.items = self._load()
        if not DATA_FILE.exists():
            self._add_samples()

    # --- Data Management ---
    def _load(self):
        if not DATA_FILE.exists(): return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            return [r for r in (normalise(x) for x in raw) if r]
        except Exception as exc:
            print(f"[!] Warning: Could not read {DATA_FILE.name}: {exc}")
            return []

    def _save(self):
        try:
            fd, tmp = tempfile.mkstemp(dir=DATA_FILE.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.items, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, DATA_FILE)
            return True
        except OSError as exc:
            print(f"[!] Error: Could not save inventory: {exc}")
            return False

    def _next_id(self):
        nums = [int(m.group(1)) for i in self.items if (m := re.fullmatch(r"MED-(\d+)", i["id"]))]
        return f"MED-{(max(nums) + 1 if nums else 1):04d}"

    def _find(self, item_id):
        item_id = item_id.strip().upper()
        return next((i for i in self.items if i["id"] == item_id), None)

    def _add_samples(self):
        have = {i["name"].lower() for i in self.items}
        entries = [e for e in SAMPLE_MEDICINES if e[0].lower() not in have]
        added = []
        for rec in make_sample_records(entries):
            item = {"id": self._next_id(), **rec}
            self.items.append(item)
            added.append(item)
        if added and self._save():
            return len(added)
        return 0

    # --- Commands ---
    def do_list(self, arg):
        """List inventory. Optional args: expired, soon, low, alert, or a search term.
        Example: list low"""
        today = date.today()
        arg = arg.strip().lower()
        filtered = []

        for item in self.items:
            state, _ = expiry_state(item, today)
            low = is_low(item)

            if arg == "expired" and state not in ("expired", "invalid"): continue
            elif arg == "soon" and state != "soon": continue
            elif arg == "low" and not low: continue
            elif arg == "alert" and (state == "ok" and not low): continue
            elif arg not in ("", "expired", "soon", "low", "alert"):
                # Search mode
                if not any(arg in str(item[k]).lower() for k in ("id", "name", "batch")):
                    continue

            filtered.append(item)

        filtered.sort(key=lambda x: x["expiry"])
        
        print("\n" + "=" * 95)
        print(f"{'ID':<10} {'Name':<28} {'Batch':<10} {'Qty':<6} {'Price':<8} {'Expiry':<12} {'Status':<16}")
        print("-" * 95)

        if not filtered:
            print("No items found matching the criteria.")
        else:
            for item in filtered:
                st = status_text(item, today)
                print(f"{item['id']:<10} {item['name'][:26]:<28} {item['batch']:<10} "
                      f"{item['qty']:<6} {item['price']:<8.2f} {item['expiry']:<12} {st:<16}")

        print("-" * 95)
        expired = sum(expiry_state(i, today)[0] in ("expired", "invalid") for i in self.items)
        soon = sum(expiry_state(i, today)[0] == "soon" for i in self.items)
        val = sum(i["qty"] * i["price"] for i in self.items)
        print(f"Total: {len(self.items)} items | Expired: {expired} | Expiring Soon: {soon} | Value: ${val:,.2f}")
        print("=" * 95 + "\n")

    def do_add(self, arg):
        """Add a new medicine interactively."""
        try:
            name = input("Medicine Name: ").strip()
            if not name: raise ValueError("Name cannot be empty.")
            
            batch = input("Batch Number: ").strip()
            if not batch: raise ValueError("Batch cannot be empty.")
            
            qty = int(input("Quantity: ").strip())
            if qty < 0: raise ValueError("Quantity must be non-negative.")
            
            price = float(input("Price per unit: ").strip())
            if price < 0: raise ValueError("Price must be non-negative.")
            
            expiry = input("Expiry Date (YYYY-MM-DD): ").strip()
            if parse_date(expiry) is None: raise ValueError("Invalid date format.")
            
            for item in self.items:
                if item["name"].lower() == name.lower() and item["batch"].lower() == batch.lower():
                    raise ValueError(f"Item '{name}' with batch '{batch}' already exists as ID {item['id']}.")

            new_item = {
                "id": self._next_id(), "name": name, "batch": batch, 
                "qty": qty, "price": round(price, 2), "expiry": expiry
            }
            self.items.append(new_item)
            if self._save():
                print(f"[+] Successfully added {name} ({new_item['id']}).")
                
        except ValueError as e:
            print(f"[!] Error: {e}")

    def do_update(self, arg):
        """Update an existing medicine. Usage: update <ID>"""
        if not arg:
            arg = input("Enter Medicine ID to update: ").strip()
            
        item = self._find(arg)
        if not item:
            print(f"[!] Item '{arg}' not found.")
            return

        print(f"Updating {item['id']} ({item['name']}). Leave blank to keep current value.")
        try:
            name = input(f"Name [{item['name']}]: ").strip() or item['name']
            batch = input(f"Batch [{item['batch']}]: ").strip() or item['batch']
            
            qty_str = input(f"Quantity [{item['qty']}]: ").strip()
            qty = int(qty_str) if qty_str else item['qty']
            if qty < 0: raise ValueError("Quantity must be non-negative.")

            price_str = input(f"Price [{item['price']:.2f}]: ").strip()
            price = float(price_str) if price_str else item['price']
            if price < 0: raise ValueError("Price must be non-negative.")

            expiry = input(f"Expiry [{item['expiry']}]: ").strip() or item['expiry']
            if parse_date(expiry) is None: raise ValueError("Invalid date format.")

            item.update({"name": name, "batch": batch, "qty": qty, "price": round(price, 2), "expiry": expiry})
            if self._save():
                print(f"[+] Successfully updated {item['id']}.")
        except ValueError as e:
            print(f"[!] Error: {e}")

    def do_adjust(self, arg):
        """Quickly adjust stock (+/-). Usage: adjust <ID>"""
        if not arg:
            arg = input("Enter Medicine ID to adjust: ").strip()
            
        item = self._find(arg)
        if not item:
            print(f"[!] Item '{arg}' not found.")
            return

        print(f"Selected: {item['id']} - {item['name']} | Current Stock: {item['qty']}")
        try:
            delta = int(input("Enter amount to adjust (e.g., 5 to add, -3 to dispense): ").strip())
            
            if item['qty'] + delta < 0:
                print(f"[!] Cannot dispense {-delta} units. Only {item['qty']} in stock.")
                return
                
            item['qty'] += delta
            if self._save():
                print(f"[+] Stock updated. New quantity for {item['name']}: {item['qty']}")
        except ValueError:
            print("[!] Invalid amount. Must be an integer.")

    def do_delete(self, arg):
        """Delete a medicine. Usage: delete <ID>"""
        if not arg:
            arg = input("Enter Medicine ID to delete: ").strip()
            
        item = self._find(arg)
        if not item:
            print(f"[!] Item '{arg}' not found.")
            return

        confirm = input(f"Delete {item['name']} (Batch {item['batch']})? (y/N): ").strip().lower()
        if confirm == 'y':
            self.items.remove(item)
            if self._save():
                print(f"[+] Item {item['id']} deleted.")

    def do_samples(self, arg):
        """Load sample medicine data."""
        count = self._add_samples()
        print(f"[+] Added {count} sample medicines." if count else "[i] All samples are already in inventory.")

    def do_exit(self, arg):
        """Exit the tracker."""
        print("Goodbye!")
        return True
        
    def do_quit(self, arg):
        """Exit the tracker."""
        return self.do_exit(arg)


if __name__ == "__main__":
    try:
        PharmacyShell().cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
