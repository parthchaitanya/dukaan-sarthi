"""Festival calendar and category priors.

Dates for 2026 are from published Hindu festival calendars. The per-category uplift
priors are demo assumptions: in production they would be learned from all Paytm
merchants of the same category ("network priors").
"""
from datetime import date

FESTIVALS = [
    # (key, display name, date, window_days_before, window_days_after)
    ("independence_day", "Independence Day", date(2026, 8, 15), 1, 0),
    ("raksha_bandhan", "Raksha Bandhan", date(2026, 8, 28), 3, 0),
    ("janmashtami", "Janmashtami", date(2026, 9, 4), 2, 0),
    ("ganesh_chaturthi", "Ganesh Chaturthi", date(2026, 9, 14), 2, 1),
    ("navratri", "Navratri", date(2026, 10, 11), 0, 8),
    ("dussehra", "Dussehra", date(2026, 10, 20), 1, 0),
    ("karwa_chauth", "Karwa Chauth", date(2026, 10, 29), 2, 0),
    ("dhanteras", "Dhanteras", date(2026, 11, 6), 1, 0),
    ("diwali", "Diwali", date(2026, 11, 8), 4, 0),
    ("bhai_dooj", "Bhai Dooj", date(2026, 11, 11), 1, 0),
    ("chhath", "Chhath Puja", date(2026, 11, 15), 3, 0),
    ("christmas", "Christmas", date(2026, 12, 25), 1, 0),
]

# Peak sales multiplier on the festival's busiest day, by merchant category.
UPLIFT = {
    "kirana":   {"independence_day": 1.05, "raksha_bandhan": 1.25, "janmashtami": 1.2, "ganesh_chaturthi": 1.15,
                 "navratri": 1.25, "dussehra": 1.3, "karwa_chauth": 1.3, "dhanteras": 1.5, "diwali": 1.9,
                 "bhai_dooj": 1.2, "chhath": 1.5, "christmas": 1.05},
    "salon":    {"independence_day": 1.0, "raksha_bandhan": 1.5, "janmashtami": 1.0, "ganesh_chaturthi": 1.1,
                 "navratri": 1.2, "dussehra": 1.3, "karwa_chauth": 2.2, "dhanteras": 1.6, "diwali": 2.0,
                 "bhai_dooj": 1.3, "chhath": 1.2, "christmas": 1.2},
    "cafe":     {"independence_day": 1.15, "raksha_bandhan": 1.05, "janmashtami": 1.05, "ganesh_chaturthi": 1.1,
                 "navratri": 1.1, "dussehra": 1.25, "karwa_chauth": 0.9, "dhanteras": 1.1, "diwali": 0.8,
                 "bhai_dooj": 1.0, "chhath": 1.0, "christmas": 1.3},
    "pharmacy": {"independence_day": 0.95, "raksha_bandhan": 1.0, "janmashtami": 1.0, "ganesh_chaturthi": 1.0,
                 "navratri": 1.05, "dussehra": 0.95, "karwa_chauth": 1.0, "dhanteras": 1.0, "diwali": 0.9,
                 "bhai_dooj": 1.0, "chhath": 1.0, "christmas": 1.0},
    "sweets":   {"independence_day": 1.3, "raksha_bandhan": 3.0, "janmashtami": 1.8, "ganesh_chaturthi": 2.0,
                 "navratri": 1.4, "dussehra": 1.8, "karwa_chauth": 1.6, "dhanteras": 2.4, "diwali": 3.5,
                 "bhai_dooj": 2.2, "chhath": 1.6, "christmas": 1.2},
}

# What to stock or plan for, by category (shown in the planner; UPI data has no item level).
STOCK_TIPS = {
    "kirana": {
        "default": ["Atta, chawal, dal", "Cooking oil", "Biscuits & namkeen"],
        "diwali": ["Dry fruits gift packs", "Diyas, candles & puja samagri", "Ghee, sugar, besan", "Namkeen & chocolates"],
        "chhath": ["Fruits, sugarcane & coconut", "Gur and wheat flour", "Soop & daura (if you stock them)"],
        "karwa_chauth": ["Puja thali items", "Mathri & sweets", "Sargi items: dry fruits, pheni"],
        "dhanteras": ["Steel utensils (small)", "Puja items", "Dry fruits"],
    },
    "salon": {
        "default": ["Hair colour stock", "Facial kits", "Disposables"],
        "karwa_chauth": ["Mehendi cones", "Bridal/party makeup kits", "Extra staff for the evening before"],
        "diwali": ["Facial & cleanup kits", "Hair spa products", "Book appointments 1 week ahead"],
    },
    "cafe": {
        "default": ["Milk & tea leaves", "Sugar", "Snacks"],
        "dussehra": ["Extra milk for mela crowd", "Samosa/pakora prep"],
        "christmas": ["Cake slices", "Hot chocolate mix"],
    },
    "pharmacy": {
        "default": ["Fever & cold medicines", "ORS", "BP/diabetes repeat medicines"],
        "diwali": ["Burn ointment & first-aid kits", "Antacids", "Asthma inhalers (smoke season)"],
        "chhath": ["ORS & electrolyte", "Antacids"],
    },
    "sweets": {
        "default": ["Milk & khoya", "Sugar & ghee", "Boxes"],
        "diwali": ["Kaju katli & dry-fruit boxes", "Gift packaging (2x usual)", "Extra karigar for 5 days", "Pre-orders for offices"],
        "dhanteras": ["Gift boxes", "Kaju katli"],
        "bhai_dooj": ["Small gift boxes", "Rasgulla & gulab jamun"],
        "karwa_chauth": ["Mathri", "Feni/pheni", "Small sweet boxes"],
        "chhath": ["Thekua ingredients", "Gur-based sweets"],
    },
}


def festival_intensity(d: date, category: str) -> tuple[float, str | None]:
    """Expected multiplier for a date from the festival calendar + category priors."""
    best, key = 1.0, None
    for k, _name, fd, before, after in FESTIVALS:
        delta = (d - fd).days
        if -before <= delta <= after:
            peak = UPLIFT[category][k]
            if k == "navratri":
                ramp = 1.0
            elif delta < 0:
                ramp = 1 - (-delta) / (before + 1) * 0.5  # build-up days
            else:
                ramp = 1.0 if delta == 0 else 0.6
            mult = 1 + (peak - 1) * ramp
            if abs(mult - 1) > abs(best - 1):
                best, key = mult, k
    return best, key
