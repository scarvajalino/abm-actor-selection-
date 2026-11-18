"""Event-indexed draws avoid dependence on call, policy or iteration order."""
import hashlib
from .config import integer

EVENT_IDS = {"seed_adoption": 400, "send": 401, "contact_priority": 402,
             "wom_adoption": 403, "parent_tie": 404}


class EventRandom:
    def __init__(self, master_seed, repetition):
        integer(master_seed, "master_seed")
        integer(repetition, "repetition")
        self.master_seed = master_seed
        self.repetition = repetition

    def uniform(self, event, month, actor_id, other_id=-1):
        key = f"Article9-M2-v1|{self.master_seed}|{self.repetition}|{EVENT_IDS[event]}|{month}|{actor_id}|{other_id}"
        raw = hashlib.blake2b(key.encode("ascii"), digest_size=8).digest()
        # Use 53 bits to make the conversion to a double explicit; range [0, 1).
        return (int.from_bytes(raw, "big") >> 11) / (1 << 53)

    def record(self):
        return {"method": "BLAKE2b-64, first 53 high bits / 2**53",
                "key_format": "Article9-M2-v1|master_seed|repetition|event_id|month|actor_id|other_id",
                "master_seed": self.master_seed, "repetition": self.repetition,
                "event_ids": EVENT_IDS, "policy_in_key": False}

