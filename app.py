"""
EcoTrack — Smart Carbon Footprint Assessment & Sustainability Advisory Platform
--------------------------------------------------------------------------------
Run with:  python app.py
Then open http://127.0.0.1:5000
"""

import random
import statistics
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "ecotrack-dev-secret-change-in-production"

# ----------------------------------------------------------------------------
# 1. EMISSION FACTORS  (kg CO2e — see problem-statement spec)
# ----------------------------------------------------------------------------

# The spec only tabulates Car(Petrol/Diesel), Bike, Bus, Train, Walk/Cycle.
# The questionnaire also asks for fuel type (Petrol/Diesel/CNG/Electric/NA)
# for *any* private vehicle (Car or Bike), so we extend the table with
# reasonable CNG/Electric factors, clearly flagged below as an assumption.
TRANSPORT_FACTORS = {
    "Car": {
        "Petrol": 0.192,
        "Diesel": 0.171,
        "CNG": 0.140,     # assumption — not in original spec table
        "Electric": 0.050,  # assumption — grid-charged EV, not in original spec table
        "Not Applicable": 0.192,
    },
    "Bike": {
        "Petrol": 0.103,
        "Diesel": 0.103,
        "CNG": 0.080,     # assumption
        "Electric": 0.020,  # assumption
        "Not Applicable": 0.103,
    },
    "Bus": 0.105,
    "Train / Metro": 0.041,
    "Walk / Cycle": 0.0,
}

ELECTRICITY_FACTOR = 0.82   # kg CO2e / kWh
LPG_FACTOR = 42.0           # kg CO2e / cylinder

DIET_BASE = {
    "Vegan": 1000,
    "Vegetarian": 1500,
    "Mixed Diet": 2000,
    "Non-Vegetarian": 2500,
}
MEAT_MEAL_FACTOR = 8  # kg CO2e per meat-based meal/week, per spec formula

WASTE_BAG_FACTOR = {
    "Small": 0.30,
    "Medium": 0.50,
    "Large": 0.75,
}

# Sustainable habit offsets (kg CO2e saved / year)
PRACTICE_OFFSETS = {
    "recycle": ("Recycle paper, plastic & metal", 120),
    "compost": ("Compost kitchen waste", 180),
    "walk_cycle": ("Walk or cycle for short trips (2+ days/week)", 35),
    "led": ("Use LED lighting in most rooms", 80),
    "solar": ("Have rooftop solar panels", 600),
    "reusable": ("Use reusable shopping bags & water bottles", 50),
}
TREE_OFFSET = 21  # kg CO2e / tree / year

TRANSPORT_MODES = ["Car", "Bike", "Bus", "Train / Metro", "Walk / Cycle"]
FUEL_TYPES = ["Petrol", "Diesel", "CNG", "Electric", "Not Applicable"]
PUBLIC_TRANSPORT_FREQ = ["Never", "Rarely", "1-2 days/week", "3-4 days/week", "5+ days/week"]
LPG_OPTIONS = [0, 0.5, 1, 2]
DIETS = ["Vegan", "Vegetarian", "Mixed Diet", "Non-Vegetarian"]
BAG_SIZES = ["Small", "Medium", "Large"]

TIPS = [
    "Switching one car trip a week to cycling can cut ~10 kg CO2e a month.",
    "LED bulbs use ~80% less energy than incandescent bulbs.",
    "A dripping tap can waste over 200 litres of water a month.",
    "Composting food scraps can cut your household waste emissions by up to 180 kg/year.",
    "Unplugging chargers when not in use trims 'phantom' electricity load.",
    "One mature tree absorbs roughly 21 kg of CO2 every year.",
    "Batch-cooking reduces both food waste and energy use.",
    "Carpooling with 3 colleagues can cut your commute emissions by ~75%.",
    "Air-drying clothes instead of tumble-drying saves significant electricity.",
    "Buying local, seasonal produce lowers transport-related food emissions.",
    "A well-maintained vehicle (correct tyre pressure, regular service) burns less fuel.",
    "Reusable bottles and bags can offset ~50 kg CO2e a year each.",
    "Rooftop solar can offset up to 600 kg CO2e per year for an average home.",
    "Reducing meat intake by even 2 meals a week adds up over a year.",
    "Public transport produces a fraction of the per-passenger emissions of a private car.",
]

# ----------------------------------------------------------------------------
# 2. SIMULATED "ANONYMOUS OTHER USERS" DATASET (for average / percentile score)
# ----------------------------------------------------------------------------
random.seed(42)
COMMUNITY_FOOTPRINTS = sorted(
    max(500, random.gauss(4300, 1400)) for _ in range(500)
)
COMMUNITY_AVERAGE = round(statistics.mean(COMMUNITY_FOOTPRINTS), 1)


def percentile_rank(value):
    """% of the community whose footprint is >= value (i.e. this user is
    better than that percentage). Lower footprint => higher percentile."""
    better_than = sum(1 for v in COMMUNITY_FOOTPRINTS if v >= value)
    return round(100 * better_than / len(COMMUNITY_FOOTPRINTS), 1)


# ----------------------------------------------------------------------------
# 3. CORE CALCULATION ENGINE
# ----------------------------------------------------------------------------

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_footprint(data):
    """
    data: dict with keys -
        transport_mode, distance_km, fuel_type,
        electricity_kwh, lpg_cylinders,
        diet, meat_meals_week,
        waste_bag_size, waste_bags_week,
        trees, practices (list)
    Returns a dict with the full breakdown.
    """
    transport_mode = data.get("transport_mode", "Walk / Cycle")
    distance_km = _to_float(data.get("distance_km"))
    fuel_type = data.get("fuel_type", "Not Applicable")

    if transport_mode in ("Car", "Bike"):
        factor = TRANSPORT_FACTORS[transport_mode].get(fuel_type, TRANSPORT_FACTORS[transport_mode]["Not Applicable"])
    else:
        factor = TRANSPORT_FACTORS.get(transport_mode, 0.0)

    transport_co2 = distance_km * factor * 12

    electricity_kwh = _to_float(data.get("electricity_kwh"))
    electricity_co2 = electricity_kwh * ELECTRICITY_FACTOR * 12

    lpg_cylinders = _to_float(data.get("lpg_cylinders"))
    lpg_co2 = lpg_cylinders * LPG_FACTOR * 12

    diet = data.get("diet", "Mixed Diet")
    diet_co2 = DIET_BASE.get(diet, DIET_BASE["Mixed Diet"])

    meat_meals_week = _to_float(data.get("meat_meals_week"))
    meat_co2 = meat_meals_week * MEAT_MEAL_FACTOR

    waste_bag_size = data.get("waste_bag_size", "Medium")
    waste_bags_week = _to_float(data.get("waste_bags_week"))
    waste_co2 = WASTE_BAG_FACTOR.get(waste_bag_size, WASTE_BAG_FACTOR["Medium"]) * waste_bags_week * 52

    gross = transport_co2 + electricity_co2 + lpg_co2 + diet_co2 + meat_co2 + waste_co2

    trees = _to_float(data.get("trees"))
    tree_offset = trees * TREE_OFFSET

    practices = data.get("practices") or []
    practice_offset_total = 0.0
    practice_breakdown = []
    for key in practices:
        if key in PRACTICE_OFFSETS:
            label, value = PRACTICE_OFFSETS[key]
            practice_offset_total += value
            practice_breakdown.append({"key": key, "label": label, "value": value})

    total_offsets = tree_offset + practice_offset_total
    net = gross - total_offsets

    breakdown = {
        "transport": round(transport_co2, 1),
        "electricity": round(electricity_co2, 1),
        "lpg": round(lpg_co2, 1),
        "diet": round(diet_co2, 1),
        "meat": round(meat_co2, 1),
        "waste": round(waste_co2, 1),
    }

    return {
        "breakdown": breakdown,
        "gross": round(gross, 1),
        "tree_offset": round(tree_offset, 1),
        "practice_offset": round(practice_offset_total, 1),
        "practice_breakdown": practice_breakdown,
        "total_offsets": round(total_offsets, 1),
        "net": round(net, 1),
    }


def generate_recommendations(profile, result):
    """Rule-based personalized advice, ranked by biggest contributor first."""
    breakdown = result["breakdown"]
    combined = dict(breakdown)
    combined["food"] = combined.pop("diet") + combined.pop("meat")
    ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)

    advice_map = {
        "transport": "Your transport emissions are a major contributor. Consider carpooling, "
                     "using public transport more often, or switching to an electric/hybrid vehicle "
                     "for a big chunk of your monthly distance.",
        "electricity": "Household electricity is a large share of your footprint. LED lighting, "
                       "efficient appliances, and (if feasible) rooftop solar can meaningfully cut this.",
        "lpg": "LPG usage is significant. Efficient cooking habits (pressure cooking, lid use) and "
               "induction cooktops for some meals can reduce cylinder consumption.",
        "food": "Diet is a top contributor. Shifting a few meat-based meals a week to vegetarian "
                "options can noticeably lower your footprint.",
        "waste": "Household waste is adding up. Composting kitchen waste and switching to smaller "
                 "bags via better segregation and recycling can help.",
    }

    tips = []
    for key, _value in ranked[:3]:
        if key in advice_map:
            tips.append(advice_map[key])

    if not profile.get("practices"):
        tips.append("You haven't logged any sustainable habits yet — even reusable bags/bottles "
                    "or LED lighting can offset 50-80 kg CO2e a year each.")
    if _to_float(profile.get("trees")) == 0:
        tips.append("Planting and maintaining even a couple of trees offsets ~21 kg CO2e/year each.")

    return tips


def major_contributors(result):
    breakdown = dict(result["breakdown"])
    breakdown["food"] = breakdown.pop("diet") + breakdown.pop("meat")
    ranked = sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(v for _k, v in ranked) or 1
    return [{"category": k, "value": v, "share": round(100 * v / total, 1)} for k, v in ranked]


# ----------------------------------------------------------------------------
# 4. ROUTES
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        transport_modes=TRANSPORT_MODES,
        fuel_types=FUEL_TYPES,
        pt_freq=PUBLIC_TRANSPORT_FREQ,
        lpg_options=LPG_OPTIONS,
        diets=DIETS,
        bag_sizes=BAG_SIZES,
        practices=PRACTICE_OFFSETS,
    )


@app.route("/submit", methods=["POST"])
def submit():
    form = request.form
    profile = {
        "name": form.get("name", "").strip() or "Eco Explorer",
        "transport_mode": form.get("transport_mode"),
        "distance_km": form.get("distance_km"),
        "fuel_type": form.get("fuel_type"),
        "pt_freq": form.get("pt_freq"),
        "electricity_kwh": form.get("electricity_kwh"),
        "lpg_cylinders": form.get("lpg_cylinders"),
        "diet": form.get("diet"),
        "meat_meals_week": form.get("meat_meals_week"),
        "waste_bag_size": form.get("waste_bag_size"),
        "waste_bags_week": form.get("waste_bags_week"),
        "trees": form.get("trees"),
        "practices": form.getlist("practices"),
    }
    session["profile"] = profile
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    profile = session.get("profile")
    if not profile:
        return redirect(url_for("index"))

    result = calculate_footprint(profile)
    percentile = percentile_rank(result["net"])
    recommendations = generate_recommendations(profile, result)
    contributors = major_contributors(result)

    return render_template(
        "dashboard.html",
        profile=profile,
        result=result,
        percentile=percentile,
        community_average=COMMUNITY_AVERAGE,
        recommendations=recommendations,
        contributors=contributors,
        tips=TIPS,
        transport_modes=TRANSPORT_MODES,
        fuel_types=FUEL_TYPES,
        diets=DIETS,
        bag_sizes=BAG_SIZES,
        practices=PRACTICE_OFFSETS,
    )


@app.route("/api/whatif", methods=["POST"])
def api_whatif():
    """Stateless recompute used by the What-If Simulator sliders."""
    data = request.get_json(force=True) or {}
    result = calculate_footprint(data)
    percentile = percentile_rank(result["net"])
    contributors = major_contributors(result)
    return jsonify({
        "result": result,
        "percentile": percentile,
        "community_average": COMMUNITY_AVERAGE,
        "contributors": contributors,
    })


@app.route("/activities")
def activities():
    profile = session.get("profile")
    if not profile:
        return redirect(url_for("index"))
    return render_template("activities.html", profile=profile)


@app.route("/learn-more")
def learn_more():
    return render_template("learn_more.html")


@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)