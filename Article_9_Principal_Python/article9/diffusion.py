"""Synchronous monthly diffusion with one lifetime message per directed edge."""
from collections import defaultdict
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from .attributes import ATTRIBUTES
from .behavior import (adoption_probability, communication_capacity, credible_signal,
                       experience_satisfaction, send_probability)
from .event_random import EventRandom

EVENT_COLUMNS = ["month", "event_id", "sender", "receiver", "sender_adoption_month",
                 "root_seed", "sender_depth", "credibility", "expertise", "expertise_fit",
                 "credible_signal", "contact_priority", "prior_wom_exposures", "first_wom_exposure",
                 "repeated_wom_exposure", "new_awareness", "receiver_adopted_this_month", "conversion_credit"]
EVALUATION_COLUMNS = ["month", "actor_id", "source", "need", "product_fit", "risk",
                      "current_max_signal", "unique_wom_senders", "adoption_probability", "adoption_draw",
                      "adopted", "satisfaction", "satisfied", "parent_id", "root_seed", "parent_event_id"]
SENDER_COLUMNS = ["month", "actor_id", "adopted_month", "satisfaction", "capacity", "eligible_contacts",
                  "send_probability", "send_draw", "sent", "messages_sent", "reason"]


@dataclass
class DiffusionResult:
    policy: str
    repetition: int
    periods: pd.DataFrame
    events: pd.DataFrame
    evaluations: pd.DataFrame
    sender_log: pd.DataFrame
    state_history: pd.DataFrame
    final_states: pd.DataFrame
    cascades: pd.DataFrame
    summary: dict


def simulate(population, selection, model_config, config, *, actor_order=None, event_random=None):
    """Targets come from M1; neither predicted scores nor hidden values enter behavior."""
    graph = population.graph
    ids = sorted(graph.nodes)
    if set(population.nodes.actor_id) != set(ids) or len(population.nodes) != len(ids):
        raise ValueError("Unique population rows must match graph nodes")
    if not ids:
        raise ValueError("Population must be nonempty")
    order = list(ids if actor_order is None else actor_order)
    if len(order) != len(ids) or set(order) != set(ids):
        raise ValueError("actor_order must be a permutation of population identifiers")
    seeds = set(selection.actor_ids)
    if len(seeds) != len(selection.actor_ids) or not seeds <= set(ids):
        raise ValueError("Initial actors must be unique population members")
    projected = population.nodes.set_index("actor_id").loc[ids, ["community_id", *ATTRIBUTES]].copy()
    values = projected[list(ATTRIBUTES)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("Behavioral attributes must be finite in [0, 1]")
    actors = projected.to_dict("index")
    neighbors = {i: sorted(graph[i]) for i in ids}
    field = event_random or EventRandom(model_config.master_seed, population.repetition)
    state = {i: {"actor_id": i, "community_id": int(actors[i]["community_id"]),
                 "selected": i in seeds, "seed_evaluated": False, "aware": False, "adopted": False,
                 "satisfaction": None, "satisfied": False, "wom_active": False,
                 "awareness_month": None, "adoption_month": None, "acquisition_source": "",
                 "parent_id": None, "root_seed": None, "cascade_depth": None,
                 "wom_exposures": 0, "unique_wom_senders": 0, "messages_sent": 0} for i in ids}
    received_from = {i: set() for i in ids}
    sent_pairs = set()
    events, evaluations, sender_log, histories, periods = [], [], [], [], []

    def available(i):
        return [j for j in neighbors[i] if not state[j]["adopted"] and (i, j) not in sent_pairs]

    def eligible(i):
        s, a = state[i], actors[i]
        return (s["adopted"] and s["satisfied"] and a["activity"] > 0 and
                a["recommendation_propensity"] > 0 and send_probability(a, s["satisfaction"]) > 0 and
                communication_capacity(a, config) > 0 and bool(available(i)))

    def adopt(i, month, source, parent=None):
        if state[i]["adopted"]:
            raise RuntimeError("A person cannot adopt twice")
        satisfaction = experience_satisfaction(actors[i], config)
        s = state[i]
        s.update(adopted=True, adoption_month=month, acquisition_source=source,
                 satisfaction=satisfaction, satisfied=satisfaction >= config.satisfaction_threshold)
        if parent is None:
            s.update(parent_id=None, root_seed=i, cascade_depth=0)
        else:
            p = state[parent]
            if not p["adopted"] or p["adoption_month"] >= month:
                raise RuntimeError("A parent must have adopted in an earlier month")
            s.update(parent_id=parent, root_seed=p["root_seed"], cascade_depth=p["cascade_depth"] + 1)

    def evaluation_row(i, month, source, signal, probability, draw, success, parent_event=None):
        a, s = actors[i], state[i]
        return {"month": month, "actor_id": i, "source": source, "need": a["need"],
                "product_fit": a["product_fit"],
                "risk": config.product_complexity * (1 - a["expertise"] * a["expertise_fit"]),
                "current_max_signal": signal, "unique_wom_senders": len(received_from[i]),
                "adoption_probability": probability, "adoption_draw": draw, "adopted": success,
                "satisfaction": s["satisfaction"] if success else None,
                "satisfied": s["satisfied"] if success else False,
                "parent_id": s["parent_id"] if success else None,
                "root_seed": s["root_seed"] if success else None,
                "parent_event_id": parent_event or ""}

    def snapshot(month, monthly_events):
        for i in ids:
            state[i]["wom_active"] = bool(eligible(i))
            row = dict(state[i])
            row["month"] = month
            row["commercial_state"] = ("satisfied_customer" if row["satisfied"] else "unsatisfied_customer") if row["adopted"] else ("aware_nonadopter" if row["aware"] else "unaware")
            histories.append(row)
        aware_ids = [i for i in ids if state[i]["aware"]]
        adopted_ids = [i for i in ids if state[i]["adopted"]]
        wom_ids = [i for i in ids if state[i]["wom_exposures"]]
        exposure_count = sum(state[i]["wom_exposures"] for i in ids)
        prior_aware = periods[-1]["awareness_count"] if periods else 0
        prior_adopted = periods[-1]["adoption_count"] if periods else 0
        periods.append({"month": month, "new_awareness": len(aware_ids) - prior_aware,
                        "awareness_count": len(aware_ids), "awareness_fraction": len(aware_ids) / len(ids),
                        "new_adoptions": len(adopted_ids) - prior_adopted,
                        "adoption_count": len(adopted_ids), "adoption_fraction": len(adopted_ids) / len(ids),
                        "seed_source_adoptions": sum(state[i]["acquisition_source"] == "seed" for i in ids),
                        "wom_source_adoptions": sum(state[i]["acquisition_source"] == "wom" for i in ids),
                        "selected_adopters": sum(state[i]["adopted"] for i in seeds),
                        "satisfied_customers": sum(state[i]["satisfied"] for i in ids),
                        "wom_messages_new": len(monthly_events), "wom_messages_cumulative": exposure_count,
                        "wom_unique_reach": len(wom_ids), "wom_unique_nonseed_reach": len(set(wom_ids) - seeds),
                        "repeated_wom_exposures": exposure_count - len(wom_ids),
                        "wom_redundancy": (exposure_count - len(wom_ids)) / exposure_count if exposure_count else 0.0,
                        "actual_senders_this_month": len({e["sender"] for e in monthly_events}),
                        "eligible_senders_next_month": sum(state[i]["wom_active"] for i in ids),
                        "communities_aware": len({state[i]["community_id"] for i in aware_ids}),
                        "communities_with_adoption": len({state[i]["community_id"] for i in adopted_ids}),
                        "communities_with_wom_exposure": len({state[i]["community_id"] for i in wom_ids})})

    snapshot(0, [])
    for month in range(1, config.horizon_months + 1):
        incoming = defaultdict(list)
        monthly_events = []
        # All sending decisions see the same start-of-month adopter set. No within-step cascade.
        for i in order:
            s, a = state[i], actors[i]
            if not s["adopted"]:
                continue
            candidates = available(i)
            capacity = communication_capacity(a, config)
            if not s["satisfied"]:
                reason = "unsatisfied"
            elif a["activity"] <= 0:
                reason = "zero_activity"
            elif a["recommendation_propensity"] <= 0:
                reason = "zero_recommendation_propensity"
            elif send_probability(a, s["satisfaction"]) <= 0:
                reason = "zero_send_probability"
            elif capacity == 0:
                reason = "zero_integer_capacity"
            elif not candidates:
                reason = "audience_exhausted"
            else:
                reason = "eligible"
            probability = send_probability(a, s["satisfaction"]) if reason == "eligible" else 0.0
            draw = field.uniform("send", month, i) if reason == "eligible" else None
            sent = reason == "eligible" and draw < probability
            targets = []
            if sent:
                ranked = sorted((field.uniform("contact_priority", month, i, j), j) for j in candidates)
                targets = ranked[:capacity]
                for priority, j in targets:
                    sent_pairs.add((i, j))
                    event = {"month": month, "event_id": f"m{month}_s{i}_r{j}", "sender": i, "receiver": j,
                             "sender_adoption_month": s["adoption_month"], "root_seed": s["root_seed"],
                             "sender_depth": s["cascade_depth"], "credibility": a["credibility"],
                             "expertise": a["expertise"], "expertise_fit": a["expertise_fit"],
                             "credible_signal": credible_signal(a, config), "contact_priority": priority,
                             "prior_wom_exposures": None, "first_wom_exposure": False,
                             "repeated_wom_exposure": False, "new_awareness": False,
                             "receiver_adopted_this_month": False, "conversion_credit": False}
                    monthly_events.append(event)
                    incoming[j].append(event)
                s["messages_sent"] += len(targets)
            sender_log.append({"month": month, "actor_id": i, "adopted_month": s["adoption_month"],
                               "satisfaction": s["satisfaction"], "capacity": capacity,
                               "eligible_contacts": len(candidates), "send_probability": probability,
                               "send_draw": draw, "sent": sent, "messages_sent": len(targets),
                               "reason": "sent" if sent else "draw_failed" if reason == "eligible" else reason})

        if month == 1:
            for i in sorted(seeds):
                state[i].update(aware=True, awareness_month=1, seed_evaluated=True)
                probability = adoption_probability(actors[i], config, source="seed")
                draw = field.uniform("seed_adoption", month, i)
                success = draw < probability
                if success:
                    adopt(i, month, "seed")
                evaluations.append(evaluation_row(i, month, "seed", 0.0, probability, draw, success))

        # Canonical event order is only for bookkeeping; adoption is evaluated once per receiver.
        for event in sorted(monthly_events, key=lambda e: (e["receiver"], e["sender"])):
            i, j = event["sender"], event["receiver"]
            prior = state[j]["wom_exposures"]
            event.update(prior_wom_exposures=prior, first_wom_exposure=prior == 0,
                         repeated_wom_exposure=prior > 0, new_awareness=not state[j]["aware"])
            state[j]["wom_exposures"] += 1
            received_from[j].add(i)
            state[j]["unique_wom_senders"] = len(received_from[j])
            if not state[j]["aware"]:
                state[j].update(aware=True, awareness_month=month)

        for j in sorted(incoming):
            messages = incoming[j]
            signal = max(e["credible_signal"] for e in messages)
            probability = adoption_probability(actors[j], config, signal, len(received_from[j]), source="wom")
            draw = field.uniform("wom_adoption", month, j)
            success = draw < probability
            parent_event = None
            if success:
                parent_event = min(messages, key=lambda e: (-e["credible_signal"],
                    field.uniform("parent_tie", month, j, e["sender"]), e["sender"]))
                adopt(j, month, "wom", parent_event["sender"])
                parent_event["conversion_credit"] = True
            for event in messages:
                event["receiver_adopted_this_month"] = success
            evaluations.append(evaluation_row(j, month, "wom", signal, probability, draw, success,
                                               parent_event["event_id"] if parent_event else None))
        events.extend(sorted(monthly_events, key=lambda e: (e["receiver"], e["sender"])))
        snapshot(month, monthly_events)

    periods_df = pd.DataFrame(periods)
    history = pd.DataFrame(histories).sort_values(["month", "actor_id"]).reset_index(drop=True)
    final = history.loc[history.month == config.horizon_months].copy().reset_index(drop=True)
    event_table = pd.DataFrame(events, columns=EVENT_COLUMNS)
    evaluation_table = pd.DataFrame(evaluations, columns=EVALUATION_COLUMNS)
    send_table = pd.DataFrame(sender_log, columns=SENDER_COLUMNS).sort_values(["month", "actor_id"]).reset_index(drop=True)
    cascade_rows = []
    for root in sorted(seeds):
        members = [i for i in ids if state[i]["root_seed"] == root]
        seed_direct = state[root]["acquisition_source"] == "seed"
        cascade_rows.append({"root_seed": root, "seed_direct_adoption": seed_direct,
                             "seed_adopted_via_wom": state[root]["acquisition_source"] == "wom",
                             "cascade_adopters_including_root": len(members),
                             "cascade_adopters_excluding_root": len(members) - int(seed_direct),
                             "max_depth": max((state[i]["cascade_depth"] for i in members), default=None),
                             "communities_with_adoption": len({state[i]["community_id"] for i in members}),
                             "wom_events": sum(e["root_seed"] == root for e in events),
                             "eligible_senders_at_end": sum(state[i]["wom_active"] for i in members)})
    cascades = pd.DataFrame(cascade_rows, columns=["root_seed", "seed_direct_adoption", "seed_adopted_via_wom",
        "cascade_adopters_including_root", "cascade_adopters_excluding_root", "max_depth",
        "communities_with_adoption", "wom_events", "eligible_senders_at_end"])
    summary = {"policy": selection.policy, "repetition": population.repetition, "n_agents": len(ids),
               "selected_count": len(seeds), **periods[-1]}
    for variable in ["awareness", "adoption"]:
        for threshold in ([.1, .25, .5, .75] if variable == "awareness" else [.1, .25, .5]):
            reached = periods_df.loc[periods_df[f"{variable}_fraction"] >= threshold, "month"]
            summary[f"month_to_{int(threshold * 100)}pct_{variable}"] = int(reached.min()) if len(reached) else None
    return DiffusionResult(selection.policy, population.repetition, periods_df, event_table,
                           evaluation_table, send_table, history, final, cascades, summary)
