"""Synthetic Indian retail dataset generator (Bharat Retail Pvt Ltd) - ALL DATA IS FICTIONAL.

* Organisations, people, e-mails, mobile numbers and PIN-code tails are generated; mobiles use a non-working 90000 series,
  e-mails use example.com, names are random first x last combinations. No real person or company is represented.
* Money is INR. GST slabs (0/5/12/18/28 %) are attached per product. `net_sales` is the taxable value (excluding GST),
  `net_amount` is the invoice value (including GST).
* Seasonality uses the Indian festival calendar (Diwali, Dussehra, Pongal/Sankranti, Eid, Holi, End-of-Season sales) and
  regional boosts, over the financial years FY 2024-25 .. today (IST).
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl

from .services.calendar_in import festival_windows, today_ist

DATA_START = dt.date(2024, 4, 1)  # start of FY 2024-25

# city, state, region, PIN prefix (3 digits), population-ish weight
CITIES = [
    ("Mumbai", "Maharashtra", "West", "400", 12), ("Pune", "Maharashtra", "West", "411", 6), ("Nagpur", "Maharashtra", "Central", "440", 2.5),
    ("Ahmedabad", "Gujarat", "West", "380", 6), ("Surat", "Gujarat", "West", "395", 4),
    ("Delhi", "Delhi", "North", "110", 12), ("Gurugram", "Haryana", "North", "122", 3), ("Chandigarh", "Chandigarh", "North", "160", 1.8),
    ("Jaipur", "Rajasthan", "North", "302", 4), ("Lucknow", "Uttar Pradesh", "North", "226", 4), ("Kanpur", "Uttar Pradesh", "North", "208", 2.5),
    ("Bengaluru", "Karnataka", "South", "560", 11), ("Mysuru", "Karnataka", "South", "570", 1.5),
    ("Hyderabad", "Telangana", "South", "500", 9), ("Chennai", "Tamil Nadu", "South", "600", 8), ("Coimbatore", "Tamil Nadu", "South", "641", 2.5),
    ("Kochi", "Kerala", "South", "682", 3), ("Vijayawada", "Andhra Pradesh", "South", "520", 3.5), ("Visakhapatnam", "Andhra Pradesh", "South", "530", 3.5),
    ("Tirupati", "Andhra Pradesh", "South", "517", 2),
    ("Kolkata", "West Bengal", "East", "700", 8), ("Bhubaneswar", "Odisha", "East", "751", 2.5), ("Patna", "Bihar", "East", "800", 3), ("Guwahati", "Assam", "East", "781", 2),
    ("Bhopal", "Madhya Pradesh", "Central", "462", 3), ("Indore", "Madhya Pradesh", "Central", "452", 3.5), ("Raipur", "Chhattisgarh", "Central", "492", 2),
]
FIRST_M = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karthik", "Sai", "Venkat", "Ravi", "Suresh", "Anil", "Rajesh", "Manoj", "Amit", "Sandeep", "Vikram", "Harish", "Naveen", "Kiran", "Pranav", "Imran", "Faisal", "Gurpreet", "Harpreet", "Subhash", "Debashish", "Abhishek", "Nikhil"]
FIRST_F = ["Ananya", "Diya", "Priya", "Lakshmi", "Kavya", "Sneha", "Pooja", "Neha", "Divya", "Meera", "Swathi", "Anjali", "Shruti", "Aishwarya", "Ritu", "Sunita", "Radha", "Bhavana", "Fatima", "Simran", "Rukmini", "Tanvi", "Ishita", "Madhavi"]
LAST = {
    "North": ["Sharma", "Verma", "Gupta", "Singh", "Yadav", "Mishra", "Kapoor", "Chopra", "Khan", "Bhatia"],
    "West": ["Patel", "Shah", "Desai", "Joshi", "Kulkarni", "Deshmukh", "Patil", "Mehta", "Naik", "Jain"],
    "South": ["Reddy", "Naidu", "Rao", "Iyer", "Nair", "Menon", "Pillai", "Krishnan", "Chowdary", "Raju", "Gowda", "Murthy"],
    "East": ["Banerjee", "Mukherjee", "Das", "Ghosh", "Sen", "Bose", "Mahapatra", "Sahoo", "Chatterjee", "Roy"],
    "Central": ["Tiwari", "Pandey", "Dubey", "Agrawal", "Chouhan", "Thakur", "Soni", "Sahu"],
}
MIDDLE = list("ABCDEFGHJKLMNPRSTVY")

# category: (gst options, sampling weight, cost ratio range, qty weights, brands, [(item, lo, hi, gst)])
CATALOG = {
    "Groceries & Staples": ([0, 5], 0.25, (0.88, 0.93), [0.4, 0.3, 0.2, 0.1], ["Annapurna", "Surya Gold", "Kaveri", "Gokul Select", "Sampoorna"], [
        ("Basmati Rice 5 kg", 380, 650, 5), ("Sona Masoori Rice 10 kg", 520, 780, 5), ("Toor Dal 1 kg", 140, 210, 0), ("Wheat Atta 10 kg", 330, 480, 0),
        ("Sugar 1 kg", 42, 58, 0), ("Sunflower Oil 1 L", 125, 175, 5), ("Mustard Oil 1 L", 150, 210, 5), ("Iodised Salt 1 kg", 22, 30, 0), ("Poha 500 g", 38, 70, 0), ("Jaggery 1 kg", 60, 95, 0)]),
    "Packaged Foods": ([12, 18], 0.17, (0.70, 0.80), [0.45, 0.3, 0.15, 0.1], ["Rasoi Ready", "Swad", "Tasty Bharat", "Nanhe Foods"], [
        ("Masala Noodles 4-pack", 48, 72, 18), ("Cream Biscuits 300 g", 30, 55, 18), ("Namkeen Mixture 400 g", 80, 130, 12), ("Pav Bhaji Ready Meal 300 g", 70, 110, 12),
        ("Mango Pickle 500 g", 90, 160, 12), ("Instant Idli Mix 500 g", 60, 95, 12), ("Corn Flakes 475 g", 150, 260, 18), ("Peanut Butter 340 g", 180, 320, 12), ("Dark Chocolate 100 g", 90, 190, 18)]),
    "Beverages": ([5, 12, 18, 28], 0.12, (0.65, 0.78), [0.4, 0.3, 0.2, 0.1], ["Chai Wala", "Malabar", "Himgiri", "Fresh Pani"], [
        ("Masala Tea 500 g", 210, 340, 5), ("Filter Coffee Powder 500 g", 320, 520, 5), ("Packaged Water 1 L x 12", 150, 260, 18), ("Mango Drink 1.2 L", 55, 85, 12),
        ("Cola 2 L", 80, 110, 28), ("Coconut Water 200 ml x 6", 180, 300, 12), ("Energy Drink 250 ml x 4", 400, 560, 28), ("Sweet Lassi 200 ml x 6", 150, 240, 12)]),
    "Personal Care": ([18], 0.13, (0.55, 0.70), [0.55, 0.3, 0.15], ["Ayur Veda", "Nirmal", "Tulsi", "Sundari"], [
        ("Herbal Shampoo 340 ml", 190, 380, 18), ("Sandalwood Soap 4-pack", 120, 210, 18), ("Neem Face Wash 100 ml", 110, 220, 18), ("Toothpaste 200 g", 95, 160, 18),
        ("Coconut Hair Oil 500 ml", 190, 320, 18), ("Body Lotion 400 ml", 240, 420, 18), ("Deodorant 150 ml", 180, 320, 18), ("Sunscreen SPF 50 60 g", 260, 520, 18)]),
    "Home Appliances": ([18, 28], 0.05, (0.78, 0.86), [0.93, 0.07], ["Kaveri Home", "Vajra", "Shakti", "Bharat Electric"], [
        ("Mixer Grinder 750 W", 2200, 5200, 18), ("Induction Cooktop", 1800, 3800, 18), ("Pressure Cooker 5 L", 1300, 2600, 18), ("Ceiling Fan 1200 mm", 1900, 4200, 18),
        ("Room Air Cooler 50 L", 7500, 14500, 28), ("Split AC 1.5 Ton", 32000, 52000, 28), ("Front Load Washing Machine 7 kg", 14000, 26000, 28), ("Refrigerator 253 L", 21000, 34000, 28),
        ("Storage Water Heater 15 L", 4800, 9500, 28), ("LED TV 43 inch", 19000, 34000, 28)]),
    "Mobiles & Electronics": ([18], 0.09, (0.85, 0.92), [0.95, 0.05], ["Zenith", "Pragati", "Nova", "Tej"], [
        ("Smartphone 6 GB/128 GB", 9500, 19500, 18), ("Smartphone 8 GB/256 GB", 22000, 48000, 18), ("Feature Phone", 1400, 2800, 18), ("Wireless Earbuds", 1200, 4500, 18),
        ("Bluetooth Speaker", 1500, 4200, 18), ("Power Bank 20000 mAh", 1400, 2400, 18), ("Smartwatch", 2500, 9000, 18), ("Laptop 15.6 inch", 38000, 72000, 18), ("Tablet 10 inch", 13000, 28000, 18), ("LED Bulb 9 W 4-pack", 260, 480, 12)]),
    "Apparel": ([5, 12], 0.10, (0.50, 0.65), [0.5, 0.3, 0.2], ["Urban Gaon", "Metro Thread", "Rangreza", "Cotton Route"], [
        ("Cotton T-Shirt", 349, 799, 5), ("Denim Jeans", 999, 2299, 12), ("Formal Shirt", 899, 1899, 12), ("Kids Wear Set", 499, 1199, 5), ("Track Pants", 599, 1299, 5),
        ("Hooded Sweatshirt", 1099, 2499, 12), ("Winter Jacket", 1799, 4599, 12), ("Innerwear Pack of 3", 299, 699, 5)]),
    "Ethnic Wear": ([5, 12], 0.09, (0.50, 0.62), [0.7, 0.25, 0.05], ["Kanchi Weaves", "Banaras Loom", "Jaipur Prints", "Lakshmi Silks"], [
        ("Silk Saree", 4999, 14999, 12), ("Cotton Saree", 999, 2999, 5), ("Salwar Kameez Set", 1299, 3499, 12), ("Men's Kurta", 799, 2199, 5), ("Sherwani Set", 7999, 19999, 12),
        ("Bridal Lehenga", 8999, 24999, 12), ("Embroidered Dupatta", 399, 1499, 5), ("Kolhapuri Chappal", 699, 1599, 12), ("Banarasi Stole", 1499, 3999, 12)]),
}
PAYMENTS = ["UPI", "Credit/Debit Card", "Net Banking", "COD", "Wallet"]
PAY_BY_CHANNEL = {"Online": [0.42, 0.24, 0.09, 0.17, 0.08], "Store": [0.52, 0.34, 0.02, 0.0, 0.12], "Marketplace": [0.34, 0.2, 0.05, 0.31, 0.10]}
REFUND_REASONS = ["Damaged item", "Wrong item delivered", "Quality issue", "Late delivery", "Size / fit issue"]


def _customers(rng: np.random.Generator, n: int) -> pl.DataFrame:
    w = np.array([c[4] for c in CITIES], dtype=float)
    ci = rng.choice(len(CITIES), n, p=w / w.sum())
    names, used = [], set()
    for i in range(n):
        city, state, region, prefix, _ = CITIES[ci[i]]
        first = rng.choice(FIRST_F if rng.random() < 0.46 else FIRST_M)
        pool = LAST[region] if rng.random() < 0.8 else LAST[rng.choice(list(LAST))]
        nm = f"{first} {rng.choice(pool)}"
        while nm in used:
            nm = f"{first} {rng.choice(MIDDLE)}. {rng.choice(pool)}"
            if nm in used:
                nm = f"{first} {rng.choice(MIDDLE)}{rng.choice(MIDDLE)}. {rng.choice(pool)}"
        used.add(nm)
        names.append(nm)
    ids = [f"C{i:05d}" for i in range(1, n + 1)]
    seg = rng.choice(["Individual", "Kirana / Small Business", "Corporate"], n, p=[0.78, 0.17, 0.05])
    return pl.DataFrame({
        "customer_id": ids, "customer_name": names,
        "mobile": [f"+91 90000 {rng.integers(0, 100000):05d}" for _ in range(n)],  # non-working demo series
        "email": [f"{nm.lower().replace(' ', '.').replace('..', '.')}.{i}@example.com" for i, nm in enumerate(names, 1)],
        "city": [CITIES[i][0] for i in ci], "state": [CITIES[i][1] for i in ci], "region": [CITIES[i][2] for i in ci],
        "pin_code": [f"{CITIES[i][3]}{rng.integers(0, 1000):03d}" for i in ci],
        "segment": seg, "signup_date": [DATA_START - dt.timedelta(days=int(d)) for d in rng.integers(30, 1100, n)],
    })


def _products(rng: np.random.Generator) -> pl.DataFrame:
    rows = []
    pid = 1
    for cat, (_gst, _w, cost_rng, _q, brands, items) in CATALOG.items():
        for item, lo, hi, gst in items:
            for b in rng.choice(brands, size=min(3, len(brands)), replace=False):
                price = round(float(rng.uniform(lo, hi) * rng.uniform(0.96, 1.06)), 2)
                rows.append((f"P{pid:04d}", f"{b} {item}", str(b), cat, price, gst, round(price * float(rng.uniform(*cost_rng)), 2)))
                pid += 1
    return pl.DataFrame(rows, schema=["product_id", "product_name", "brand", "category", "unit_price", "gst_rate", "unit_cost"], orient="row")


def _day_weights(days: list[dt.date]) -> np.ndarray:
    n = len(days)
    w = np.array([(1 + 0.8 * i / n) * (1.08 if d.weekday() >= 5 else 1.0) * (1.1 if d.day <= 7 else 1.0) for i, d in enumerate(days)])
    idx = {d: i for i, d in enumerate(days)}

    def boost(start: dt.date, end: dt.date, peak: float):
        span = max((end - start).days, 1)
        for k in range((end - start).days + 1):
            d = start + dt.timedelta(days=k)
            if d in idx:
                x = 1 - abs((k / span) - 0.78)  # ramp up to just before the festival day
                w[idx[d]] *= 1 + (peak - 1) * max(x, 0.35)

    yrs = range(DATA_START.year, days[-1].year + 1)
    for name, peak in (("diwali", 2.5), ("dussehra", 1.7), ("sankranti", 1.45), ("eid", 1.4), ("holi", 1.3), ("eoss", 1.5)):
        for s, e in festival_windows(name, yrs):
            boost(s, e, peak)
    return w / w.sum()


def gen_frames(n_lines: int = 62000, seed: int = 42) -> dict[str, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    today = today_ist()
    days = [DATA_START + dt.timedelta(days=i) for i in range((today - DATA_START).days + 1)]
    customers = _customers(rng, 5000)
    products = _products(rng)
    n_cust = customers.height
    cust_state = customers["state"].to_numpy()
    cust_region = customers["region"].to_numpy()

    n_orders = int(n_lines / 1.9)
    day_idx = rng.choice(len(days), n_orders, p=_day_weights(days))
    order_dates = [days[i] for i in day_idx]
    # heavy-tailed customer activity so "top customers" are meaningful
    cw = 1.0 / np.arange(1, n_cust + 1) ** 0.62
    cw = rng.permutation(cw / cw.sum())
    order_cust = rng.choice(n_cust, n_orders, p=cw)
    # regional festival effects: Pongal/Sankranti boosts South, Holi boosts North/Central
    south = np.where(cust_region == "South")[0]
    northc = np.where(np.isin(cust_region, ["North", "Central"]))[0]
    pong = {s: e for s, e in festival_windows("sankranti", range(DATA_START.year, today.year + 1))}
    holi = festival_windows("holi", range(DATA_START.year, today.year + 1))
    for i, d in enumerate(order_dates):
        if any(s <= d <= e for s, e in pong.items()) and rng.random() < 0.45:
            order_cust[i] = rng.choice(south)
        elif any(s <= d <= e for s, e in holi) and rng.random() < 0.35:
            order_cust[i] = rng.choice(northc)
    order_channel = rng.choice(["Online", "Store", "Marketplace"], n_orders, p=[0.40, 0.30, 0.30])
    order_pay = np.empty(n_orders, dtype=object)
    for ch, probs in PAY_BY_CHANNEL.items():
        m = order_channel == ch
        p = np.array(probs, dtype=float)
        reg = cust_region[order_cust[m]]
        base = np.tile(p, (m.sum(), 1))
        cod_boost = np.where(np.isin(reg, ["Central", "East"]), 1.45, np.where(reg == "South", 0.85, 1.0))
        base[:, 3] *= cod_boost
        base /= base.sum(axis=1, keepdims=True)
        u = rng.random(m.sum())[:, None]
        order_pay[m] = np.array(PAYMENTS, dtype=object)[(u > base.cumsum(axis=1)).sum(axis=1).clip(0, 4)]
    unit_by_ch = {"Store": None}
    bu = np.where(order_channel == "Store", np.where(rng.random(n_orders) < 0.15, "Distribution", "Retail"), "E-commerce")

    line_order = np.sort(rng.integers(0, n_orders, n_lines))
    cat_names = list(CATALOG)
    cat_w = np.array([CATALOG[c][1] for c in cat_names])
    pcat = products["category"].to_numpy()
    by_cat = {c: np.where(pcat == c)[0] for c in cat_names}
    line_cat = rng.choice(len(cat_names), n_lines, p=cat_w / cat_w.sum())
    line_prod = np.empty(n_lines, dtype=int)
    qty = np.ones(n_lines, dtype=int)
    for ci_, c in enumerate(cat_names):
        m = line_cat == ci_
        line_prod[m] = rng.choice(by_cat[c], m.sum())
        qw = np.array(CATALOG[c][3], dtype=float)
        qty[m] = rng.choice(np.arange(1, len(qw) + 1), m.sum(), p=qw / qw.sum())
    price = products["unit_price"].to_numpy()[line_prod]
    gstr = products["gst_rate"].to_numpy()[line_prod].astype(float)
    ucost = products["unit_cost"].to_numpy()[line_prod]
    line_date = np.array([order_dates[o] for o in line_order], dtype=object)
    festive = np.array([any(s <= d <= e for s, e in festival_windows("diwali", range(d.year - 1, d.year + 1)) + festival_windows("dussehra", range(d.year - 1, d.year + 1))) for d in line_date])
    disc_p = np.where(festive, 0.55, 0.28)
    disc_depth = np.where(festive, rng.uniform(0.05, 0.30, n_lines), rng.uniform(0.03, 0.15, n_lines))
    gross = np.round(qty * price, 2)
    discount = np.where(rng.random(n_lines) < disc_p, np.round(gross * disc_depth, 2), 0.0)
    net = np.round(gross - discount, 2)  # taxable value, excluding GST
    gst_amt = np.round(net * gstr / 100, 2)
    net_amt = np.round(net + gst_amt, 2)
    cost = np.round(qty * ucost, 2)
    pay = order_pay[line_order]
    cat_line = np.array(cat_names, dtype=object)[line_cat]
    base_rate = np.where(pay == "COD", 0.09, 0.034) * np.where(np.isin(cat_line, ["Apparel", "Ethnic Wear"]), 1.8, np.where(cat_line == "Home Appliances", 0.6, 1.0))
    refunded = rng.random(n_lines) < base_rate
    refund = np.where(refunded, np.round(net * rng.uniform(0.4, 1.0, n_lines), 2), 0.0)
    reason = np.full(n_lines, None, dtype=object)
    for i in np.where(refunded)[0]:
        if pay[i] == "COD" and rng.random() < 0.6:
            reason[i] = "COD return (customer refused)"
        else:
            opts = REFUND_REASONS if cat_line[i] in ("Apparel", "Ethnic Wear") else REFUND_REASONS[:4]
            reason[i] = rng.choice(opts)
    oc = order_cust[line_order]
    cust_name = customers["customer_name"].to_numpy()
    sales = pl.DataFrame({
        "order_id": [f"BR{o + 240001}" for o in line_order],
        "order_date": line_date.tolist(),
        "customer_id": customers["customer_id"].to_numpy()[oc], "customer_name": cust_name[oc],
        "product_id": products["product_id"].to_numpy()[line_prod], "product_name": products["product_name"].to_numpy()[line_prod],
        "category": cat_line.astype(str),
        "city": customers["city"].to_numpy()[oc], "state": cust_state[oc], "region": cust_region[oc],
        "channel": order_channel[line_order], "business_unit": bu[line_order], "payment_method": pay.astype(str),
        "quantity": qty.astype(np.int32), "unit_price": price, "gross_sales": gross, "discount": discount, "net_sales": net,
        "gst_rate": gstr.astype(np.int32), "gst_amount": gst_amt, "net_amount": net_amt, "cost": cost, "refund_amount": refund,
        "refund_reason": [r if r is not None else None for r in reason],
    }, schema_overrides={"order_date": pl.Date, "refund_reason": pl.String})

    orders = sales.group_by("order_id").agg(
        pl.col("order_date").first(), pl.col("customer_id").first(), pl.col("customer_name").first(), pl.col("channel").first(), pl.col("payment_method").first(),
        pl.col("city").first(), pl.col("state").first(), pl.col("region").first(), pl.len().alias("line_items"), pl.col("quantity").sum().alias("units"),
        pl.col("net_sales").sum().round(2).alias("taxable_value"), pl.col("net_amount").sum().round(2).alias("order_value"), (pl.col("refund_amount").sum() > 0).alias("has_refund"),
    ).sort("order_date")
    st = rng.choice(["Delivered", "Shipped", "Cancelled"], orders.height, p=[0.89, 0.06, 0.05])
    st = np.where(orders["has_refund"].to_numpy() & (rng.random(orders.height) < 0.5), "Returned", st)
    orders = orders.with_columns(pl.Series("status", st)).drop("has_refund")

    rf = sales.filter(pl.col("refund_amount") > 0).select("order_id", "product_id", "order_date", "refund_amount", "refund_reason", "payment_method", "state")
    lag = rng.integers(1, 22, rf.height)
    refunds = rf.with_columns(
        pl.Series("refund_id", [f"RF{i:06d}" for i in range(1, rf.height + 1)]),
        (pl.col("order_date") + pl.duration(days=pl.Series(lag))).alias("refund_date"),
    ).rename({"refund_reason": "reason"}).select("refund_id", "order_id", "product_id", "refund_date", "refund_amount", "reason", "payment_method", "state")
    departments = pl.DataFrame({
        "department_id": [f"D{i}" for i in range(1, 6)], "name": ["Sales", "Finance", "Operations", "Marketing", "Supply Chain"],
        "head": ["Anita Deshpande", "Ramesh Subramanian", "Sunil Chawla", "Lavanya Krishnan", "Mohan Pillai"], "annual_budget_inr": [24000000.0, 11500000.0, 32000000.0, 18000000.0, 27500000.0],
    })
    cust_out = customers
    return {"sales_transactions": sales, "orders": orders, "customers": cust_out, "products": products, "refunds": refunds, "departments": departments}


def gen_dispatches(seed: int = 7) -> pl.DataFrame:
    """Second workspace: Sagar Foods & Beverages Ltd (fictional FMCG manufacturer) distributor dispatches."""
    rng = np.random.default_rng(seed)
    today = today_ist()
    n = 8000
    days = (today - DATA_START).days + 1
    dists = ["Sri Lakshmi Traders", "Gupta Wholesale Mart", "Patel & Sons Distributors", "Kaveri Agencies", "Sharma Distribution Co", "Bengal Foods Depot", "Deccan Supply Hub", "Rajputana Traders"]
    depots = [("Hyderabad", "Telangana"), ("Vijayawada", "Andhra Pradesh"), ("Chennai", "Tamil Nadu"), ("Bengaluru", "Karnataka"), ("Pune", "Maharashtra"), ("Jaipur", "Rajasthan"), ("Kolkata", "West Bengal"), ("Lucknow", "Uttar Pradesh")]
    di = rng.integers(0, len(depots), n)
    cases = rng.integers(10, 400, n)
    rate = rng.choice([420.0, 560.0, 780.0, 1150.0], n)
    value = np.round(cases * rate, 2)
    return pl.DataFrame({
        "dispatch_id": [f"DSP{i:06d}" for i in range(1, n + 1)],
        "dispatch_date": [DATA_START + dt.timedelta(days=int(d)) for d in rng.integers(0, days, n)],
        "distributor_name": rng.choice(dists, n), "depot_city": [depots[i][0] for i in di], "state": [depots[i][1] for i in di],
        "product_line": rng.choice(["Packaged Foods", "Beverages", "Snacks", "Dairy & Frozen"], n, p=[0.35, 0.3, 0.25, 0.1]),
        "cases": cases.astype(np.int32), "invoice_value": value, "gst_amount": np.round(value * rng.choice([0.05, 0.12, 0.18], n), 2),
        "delivery_days": np.round(rng.gamma(2.2, 1.4, n), 1), "status": rng.choice(["Delivered", "In Transit", "Delayed"], n, p=[0.82, 0.11, 0.07]),
    }, schema_overrides={"dispatch_date": pl.Date})
