import math

KPIS_ALL = [
    ("3 mi # Competitors", "+", 0.220, 4.27, 0.0),
    ("1 mi Pop", "+", 0.218,13759.58, 929.0),
    ("3 mi daytime Pop", "+", 0.218, 81984.43,15520.0),
    ("3 mi Pop", "+", 0.208, 85725.88, 16953.0),
    ("1 mi Employee Count", "+", 0.190, 7266.52, 84.0),
    ("5 mi daytime Pop", "+", 0.171, 169971.49, 20803.0),
    ("3 mi Employee Count", "+", 0.168, 40013.33, 3245.0),
    ("5 mi Pop", "+", 0.135, 176870.88, 21652.0),
    ("1 mi White Pop (%)", "+", 0.12, 0.5074, 0.1390),
    ("Visibility", "+", 0.118, 0.389, 0.0), 
    ("City Work from Home pct", "+", 0.117, 0.1856, 0.0660),
    ("1 mi # Competitors", "+", 0.111, 1.94, 0.0),
    ("1 mi Asian Pop (%)", "-", -0.107, 0.1592, 0.6120),
    ("3 mi Asian Pop (%)", "-", -0.09, 0.1508, 0.555),
    ("1 mi hh discretionary spending", "+", 0.086, 14560.97, 6203.0),
    ("5 mi median age", "+", 0.081, 40.78, 29.8),
    ("5 mi Asian Pop (%)", "-", -0.078, 0.1561, 0.505),
    ("3 mi median hh income", "-", -0.077, 108461.86, 198058.0),
    ("End Cap", "-", -0.077, 0.37, 1.0),
    ("5 mi Employee Count", "+", 0.074, 92122.32, 6048.0),
]
KPIS_ABOVE_AVG = [
    ("1 mi Employee Count", "+", 0.3770, 7226.53, 84.0),
    ("3 mi # Competitors", "+", 0.330, 4.53, 0.0),
    ("1 mi daytime Pop", "+", 0.329, 16251.65, 918.0),
    ("1 mi median age", "-", -0.3248, 41.79, 76.50),
    ("1 mi Pop", "+", 0.286, 14882.0, 929.0),
    ("3 mi Pop", "+", 0.275, 92063.23, 21189.0),
    ("3 mi daytime Pop", "+", 0.272, 88903.35, 20074.0),
    ("3 mi Employee Count", "+", 0.257, 42338.7, 3245.0),
    ("5 mi Pop", "+", 0.256, 181932.1, 21652.0),
    ("5 mi Black Pop (%)", "+", 0.232, 0.0420, 0.003),
    ("3 mi median hh income", "-", -0.228, 110191.6, 178231.0),
    ("5 mi White Collar (%)", "+", 0.224, 0.849, 0.657),
    ("5 mi daytime Pop", "+", 0.214, 180011.15, 20803.0),
    ("3 mi Black Pop (%)", "+", 0.210, 0.0403, 0.0003),
    ("1 mi median hh income", "-", -0.196, 109701.375, 192583.0),
    ("City Work from Home pct", "+", 0.189, 0.189, 0.081),
    ("5 mi Employee Count", "+", 0.176, 92806.96, 7075.0),
    ("3 mi Blue Collar (%)", "-", -0.168, 0.13, 0.322),
    ("1 mi Black Pop (%)", "+", 0.1615, 0.035, 0.0),
    ("3 mi White Collar (%)", "+", 0.161, 0.8677, 0.678),
    ("1 mi White Collar (%)", "-", -0.146, 0.9313, 0.99),
]
KPI_ABOVE_950K = [
    ("1 mi White Collar (%)", "+", 0.392, 0.9259, 0.884),
    ("1 mi Blue Collar (%)", "-", -0.392, 0.074, 0.118),
    ("End Cap", "+", 0.350, 0.46, 0.0),
    ("1 mi Black Pop (%)", "+", 0.3149, 0.038, 0.002),
    ("5 mi White Collar (%)", "-", -0.3061, 0.882, 0.941),
    ("3 mi median age", "-", -0.3030, 41.4, 48.0),
    ("1 mi median age", "-", -0.267, 39.5, 49.6),
    ("3 mi Black Pop (%)", "+", 0.244, 0.047, 0.0003),
    ("5 mi Employee Count", "-", -0.203, 137562.54, 605734.0),
    ("5 mi daytime Pop", "-", -0.1992, 242769.77, 591123.0),
    ("3 mi median hh income", "-", -0.196, 104108.77, 176386.0),
    ("5 mi median age", "-", -0.188, 42.0, 51.40),
    ("1 mi median hh income", "-", -0.187, 104225.0, 157434.0),
    ("1 mi Asian Pop (%)", "-", -0.175, 0.153, 0.525),
    ("1 mi Pop", "-", -0.1632, 19987.31, 49842.0),
    ("1 mi hh discretionary spending", "-", -0.1536, 12468.69, 17310.0),
    ("3 mi Employee Count", "-", -0.1527, 66729.93,277446.0),
    ("5 mi Blue Collar (%)", "+", 0.1516, 0.132, 0.059),
    ("5 mi Pop", "-", -0.151, 246304.31, 609782.0)
]

def _clamp(v,lo,hi):
    return max(lo,min(hi,v))

def _kpi_score(value,direction,r_value,avg,threshold,weight):
    if value is None:
        return None
    w100 = weight * 100
    cap_thresh = w100 * 0.4
    cap_avg = w100 * 0.6
    if r_value > 0:
        denom_t = (avg-threshold) if (avg-threshold) != 0 else 1
        thresh_part = ((value-threshold) / denom_t) * cap_thresh
        avg_part = (value/avg if avg else 0) * (w100 * 0.3)
    else:
        denom_t = (threshold - avg) if (threshold - avg) != 0 else 1
        thresh_part = ((threshold - value) / denom_t) * cap_thresh
        avg_part = (2-(value/avg if avg else 0)) * (w100 * 0.3)
    thresh_part = _clamp(thresh_part,0,cap_thresh)
    avg_part = _clamp(avg_part,0,cap_avg)
    return thresh_part + avg_part

def _score_with_kpis(kpis,values):
    sum_r2 = sum(r * r for (_,_,r,_,_) in kpis)
    breakdown = []
    missing = []
    final = 0.0
    for kpi_key, direction, r_value, avg, threshold in kpis:
        weight = (r_value * r_value) / sum_r2
        value = values.get(kpi_key)
        kpi_score = _kpi_score(value, direction, r_value, avg, threshold, weight)
        if kpi_score is None:
            missing.append(kpi_key)
            breakdown.append({
                "kpi": kpi_key, "value": None,
                "weight_pct": round(weight * 100,2), "score": None,
            })
        else:
            final += kpi_score
            breakdown.append({
                "kpi": kpi_key, "value": value,
                "weight_pct": round(weight * 100,2),
                "score": round(kpi_score,3),
                "max": round(weight * 100,3),
            })
    return {
        "final_score": round(final,2),
        "missing": missing,
        "breakdown": breakdown,
    }

def score_all_locations(values):
    return _score_with_kpis(KPIS_ALL, values)
def score_above_avg(values):
    return _score_with_kpis(KPIS_ABOVE_AVG, values)
def score_above_950k(values):
    return _score_with_kpis(KPI_ABOVE_950K, values)

def profile_to_kpi_values(profile,manual_inputs = None):
    manual_inputs = manual_inputs or {}
    r1 = profile.get("ring_1mi", {}) or {}
    r3 = profile.get("ring_3mi", {}) or {}
    r5 = profile.get("ring_5mi", {}) or {}

    def _frac(pct):
        return None if pct is None else pct/100.0

    v = {
        "1 mi Pop": r1.get("population"),
        "3 mi Pop": r3.get("population"),
        "5 mi Pop": r5.get("population"),
        "1 mi daytime Pop": r1.get("daytime_population"),
        "3 mi daytime Pop": r3.get("daytime_population"),
        "5 mi daytime Pop": r5.get("daytime_population"),
        "1 mi Employee Count": r1.get("employee_count"),
        "3 mi Employee Count": r3.get("employee_count"),
        "5 mi Employee Count": r5.get("employee_count"),
        "1 mi median age": r1.get("median_age"),
        "3 mi median age": r3.get("median_age"),
        "5 mi median age": r5.get("median_age"),
        "1 mi median hh income": r1.get("median_hh_income"),
        "3 mi median hh income": r3.get("median_hh_income"),
        "5 mi median hh income": r5.get("median_hh_income"),
        "1 mi hh discretionary spending": r1.get("hh_discretionary_spend"),
        "3 mi hh discretionary spending": r3.get("hh_discretionary_spend"),
        "5 mi hh discretionary spending": r5.get("hh_discretionary_spend"),
        "1 mi hh dining spending": r1.get("hh_dining_spend"),
        "3 mi hh dining spending": r3.get("hh_dining_spend"),
        "5 mi hh dining spending": r5.get("hh_dining_spend"),
        "1 mi White Collar (%)": _frac(r1.get("white_collar_pct")),
        "3 mi White Collar (%)": _frac(r3.get("white_collar_pct")),
        "5 mi White Collar (%)": _frac(r5.get("white_collar_pct")),
        "1 mi Blue Collar (%)": _frac(r1.get("blue_collar_pct")),
        "3 mi Blue Collar (%)": _frac(r3.get("blue_collar_pct")),
        "5 mi Blue Collar (%)": _frac(r5.get("blue_collar_pct")),
        "1 mi Asian Pop (%)": _frac(r1.get("asian_pct")),
        "3 mi Asian Pop (%)": _frac(r3.get("asian_pct")),
        "5 mi Asian Pop (%)": _frac(r5.get("asian_pct")),
        "1 mi White Pop (%)": _frac(r1.get("white_pct")),
        "3 mi White Pop (%)": _frac(r3.get("white_pct")),
        "5 mi White Pop (%)": _frac(r5.get("white_pct")),
        "1 mi Black Pop (%)": _frac(r1.get("black_pct")),
        "3 mi Black Pop (%)": _frac(r3.get("black_pct")),
        "5 mi Black Pop (%)": _frac(r5.get("black_pct")),
        "City Work from Home pct": _frac(profile.get("wfh_pct")),
    }
    v.update({
        "1 mi # Competitors": manual_inputs.get("1 mi competitors"),
        "3 mi # Competitors": manual_inputs.get("3 mi competitors"),
        "End Cap": manual_inputs.get("End Cap"),
        "In Line": manual_inputs.get("In Line"),
        "Visibility": manual_inputs.get("Visibility"),
    })
    return v
def score_profile(profile, manual_inputs =None):
    values = profile_to_kpi_values(profile,manual_inputs)
    scores = {
        "vs_all_locations":score_all_locations(values),
        "vs_above_average": score_above_avg(values),
        "vs_above_950k": score_above_950k(values),
        "kpi_values": values
    }
    scores["aggregate"] = aggregate_score(scores)
    return scores

def aggregate_score(scores_dict):
    all_loc = scores_dict["vs_all_locations"]["final_score"]
    above_avg = scores_dict["vs_above_average"]["final_score"]
    above_950k = scores_dict["vs_above_950k"]["final_score"]

    avg = (all_loc +above_avg +above_950k) / 3
    sigmoid = 100/(1+math.exp(-0.1 * (avg-50)))
    return {
        "average_of_three": round(avg,2),
        "aggregate_score": round(sigmoid,2)
    }


if __name__ == "__main__":
    wausau = {
        "1 mi Pop": 10992.0, "3 mi Pop": 40301.0, "5 mi Pop": 66273.0,
        "1 mi daytime Pop": 13893.0, "3 mi daytime Pop": 47965.0, "5 mi daytime Pop": 66524.0,
        "1 mi median age": 37.5, "3 mi median age": 40.1, "5 mi median age": 40.7,
        "1 mi White Collar (%)": 0.9415434694,
        "3 mi White Collar (%)": 0.8397391799,
        "5 mi White Collar (%)": 0.8314235441,
        "1 mi Blue Collar (%)": 0.05845653058,
        "3 mi Blue Collar (%)": 0.1602608201,
        "5 mi Blue Collar (%)": 0.1685764559,
        "1 mi Asian Pop (%)": 0.1201783115,
        "3 mi Asian Pop (%)": 0.1171434952,
        "1 mi Black Pop (%)": 0.01255458515,
        "3 mi Black Pop (%)": 0.008089129302,
        "5 mi Black Pop (%)": 0.006624115401,
        "5 mi Black Pop (%) [labeled 1mi in sheet]": 0.006624115401,
        "1 mi Employee Count": 7373.0,
        "3 mi Employee Count": 33433.0,
        "5 mi Employee Count": 46602.0,
        "1 mi median hh income": 48274.0,
        "1 mi hh dining spending": 2641.0,
        "1 mi hh discretionary spending": 7958.0,
        "3 mi hh dining spending": 2976.0,
        "3 mi hh discretionary spending": 8855.0,
        "5 mi hh dining spending": 3109.0,
        "5 mi hh discretionary spending": 9276.0,
        "City Work from Home pct": 0.13,
        "1 mi # Competitors": 1.0,
        "3 mi # Competitors": 4.0,
        "End Cap": 1.0,
        "In Line": 0.0,
        "Visibility": 1.0,
    }
 
    expected = {"all": 53.57, "above_avg": 57.42, "above_950k": 48.16}
 
    print("=" * 60)
    print("VERIFICATION  —  132 Wausau (sheet's reference test case)")
    print("=" * 60)
 
    cases = [
        ("vs All Locations", score_all_locations, "all"),
        ("vs Above Avg",     score_above_avg, "above_avg"),
        ("vs Above 950K",    score_above_950k, "above_950k"),
    ]
    for label, fn, key in cases:
        result = fn(wausau)
        got = result["final_score"]
        exp = expected[key]
        diff = got - exp
        status = "PASS" if abs(diff) < 0.5 else "FAIL"
        print(f"  [{status}] {label:<22} expected {exp:>6.2f}  got {got:>6.2f}  diff {diff:+.2f}")
        if result["missing"]:
            print(f"         missing KPIs: {result['missing']}")
 
    print()
    print("Run `python scoring.py` to re-verify after edits.")