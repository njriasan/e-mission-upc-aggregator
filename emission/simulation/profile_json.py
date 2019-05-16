import json
import emission.simulation.gen_profile as gp

def to_json(p):
    return {"aggs": list(p.aggs), "algs": p.algs, "agg_alg_map": p.agg_alg_map, "default_algs": list(p.default_algs), "privacy_budget": p.privacy_budget}

def from_json(data):
    p = gp.AlgProfile ()
    p.aggs = data["aggs"]
    p.algs = data["algs"]
    p.agg_alg_map = data["agg_alg_map"]
    p.default_algs = data["default_algs"]
    p.privacy_budget = data["privacy_budget"]
    return p