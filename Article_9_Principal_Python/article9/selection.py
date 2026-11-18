"""Seven policies using only a projected ex-ante information table."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .config import integer
from .scores import EX_ANTE_COLUMNS, PURE_SCORES

POLICIES = ("random", *PURE_SCORES, "community_diversified", "hybrid")
SELECTION_COLUMNS = ["policy", "actor_id", "selection_order", "score_name", "score_value",
                     "component", "component_quota", "community_id", "activation_cost"]
AUDIT_COLUMNS = ["policy", "decision_order", "actor_id", "component", "accepted", "reason"]


@dataclass
class SelectionResult:
    policy: str
    selected: pd.DataFrame
    audit: pd.DataFrame
    quotas: dict
    component_order: list

    @property
    def actor_ids(self):
        return self.selected.actor_id.astype(int).tolist()


def ranking(nodes, score):
    return nodes.sort_values([score, "tie_rank"], ascending=[False, True]).index.tolist()


def apportion(total, weights, tie_order):
    """Largest remainder allocation. Keys are stable community/component identifiers."""
    keys = list(weights)
    if total == 0:
        return dict.fromkeys(keys, 0)
    denominator = sum(weights.values())
    if denominator <= 0:
        raise ValueError("Cannot allocate positive slots to zero capacity")
    raw = {key: total * weights[key] / denominator for key in keys}
    counts = {key: int(np.floor(raw[key])) for key in keys}
    tie_rank = {key: rank for rank, key in enumerate(tie_order)}
    priority = sorted(keys, key=lambda key: (-round(raw[key] - counts[key], 14), tie_rank[key]))
    for key in priority[:total - sum(counts.values())]:
        counts[key] += 1
    return counts


def select_actors(nodes, policy, k, streams, config):
    """Return a new selection. Receives neither hidden values nor campaign state."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")
    integer(k, "k")
    data = nodes.loc[:, list(EX_ANTE_COLUMNS)].copy().set_index("actor_id", drop=False).sort_index()
    if not data.index.is_unique or k > len(data):
        raise ValueError("Unique eligible actors and 0 <= k <= N are required")
    if data.tie_rank.nunique() != len(data):
        raise ValueError("tie_rank must uniquely order all actors")
    score_fields = [*PURE_SCORES.values(), "combined_score"]
    if not np.isfinite(data[score_fields].to_numpy()).all():
        raise ValueError("Selection scores must be finite")
    selected, audit, chosen = [], [], set()
    quotas, order = {}, []

    def log(actor, component, accepted, reason):
        audit.append({"policy": policy, "decision_order": len(audit) + 1,
                      "actor_id": int(actor), "component": component,
                      "accepted": accepted, "reason": reason})

    def accept(actor, component, score=None, quota=None):
        actor = int(actor)
        if actor in chosen:
            raise RuntimeError("Duplicate actor selected")
        chosen.add(actor)
        row = data.loc[actor]
        selected.append({"policy": policy, "actor_id": actor,
                         "selection_order": len(selected) + 1,
                         "score_name": score or "", "score_value": float(row[score]) if score else np.nan,
                         "component": component, "component_quota": quota,
                         "community_id": int(row.community_id), "activation_cost": float(row.activation_cost)})
        log(actor, component, True, "selected")

    if policy == "random":
        draw = streams.rng("random_selection").choice(data.index.to_numpy(), size=k, replace=False)
        for actor in draw:
            accept(actor, "random")
        for actor in data.index:
            if actor not in chosen:
                log(actor, "random", False, "not_sampled")
    elif policy in PURE_SCORES:
        score = PURE_SCORES[policy]
        ids = ranking(data, score)
        for position, actor in enumerate(ids):
            if position < k:
                accept(actor, policy, score)
            else:
                log(actor, policy, False, "below_cutoff")
    elif policy == "community_diversified":
        groups = sorted(int(x) for x in data.community_id.unique())
        order = streams.rng("community_ties").permutation(groups).tolist()
        sizes = data.groupby("community_id").size().to_dict()
        quotas = dict.fromkeys(groups, 0)
        if k >= len(groups):
            remaining = {group: sizes[group] - 1 for group in groups}
            extra = apportion(k - len(groups), remaining, order)
            quotas = {group: 1 + extra[group] for group in groups}
        elif k:
            for group in streams.rng("community_sample").choice(groups, size=k, replace=False):
                quotas[int(group)] = 1
        for group in groups:
            members = data.loc[data.community_id == group]
            for position, actor in enumerate(ranking(members, "combined_score")):
                if position < quotas[group]:
                    accept(actor, f"community_{group}", "combined_score", quotas[group])
                else:
                    log(actor, f"community_{group}", False, "below_community_quota")
    else:
        components = list(PURE_SCORES)
        tie_order = streams.rng("hybrid_ties").permutation(components).tolist()
        order = streams.rng("hybrid_order").permutation(components).tolist()
        quotas = apportion(k, dict(zip(components, config.hybrid_weights)), tie_order)
        lists = {component: ranking(data, PURE_SCORES[component]) for component in components}
        positions = dict.fromkeys(components, 0)
        allocated = dict.fromkeys(components, 0)
        while len(selected) < k:
            for component in order:
                if allocated[component] == quotas[component]:
                    continue
                candidates = lists[component]
                while candidates[positions[component]] in chosen:
                    actor = candidates[positions[component]]
                    log(actor, component, False, "duplicate_skipped")
                    positions[component] += 1
                actor = candidates[positions[component]]
                positions[component] += 1
                accept(actor, component, PURE_SCORES[component], quotas[component])
                allocated[component] += 1
        for component in components:
            for actor in lists[component][positions[component]:]:
                log(actor, component, False, "not_examined_after_quota")

    if len(chosen) != k:
        raise RuntimeError("Selection did not fill k unique slots")
    return SelectionResult(policy, pd.DataFrame(selected, columns=SELECTION_COLUMNS),
                           pd.DataFrame(audit, columns=AUDIT_COLUMNS), quotas, order)

