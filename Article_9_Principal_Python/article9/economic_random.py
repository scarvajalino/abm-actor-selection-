"""Separate keyed stream: economic draws never consume M1/M2 randomness."""
import hashlib
from .config import integer


class EconomicRandom:
    def __init__(self, master_seed, repetition):
        integer(master_seed, "master_seed")
        integer(repetition, "repetition")
        self.master_seed, self.repetition = master_seed, repetition

    def uniform(self, month, actor_id):
        key = f"Article9-M3-v1|{self.master_seed}|{self.repetition}|500|{month}|{actor_id}"
        digest = hashlib.blake2b(key.encode("ascii"), digest_size=8).digest()
        return (int.from_bytes(digest, "big") >> 11) / (1 << 53)

    def record(self):
        return {"method": "BLAKE2b-64, first 53 high bits / 2**53", "event_id": 500,
                "key_format": "Article9-M3-v1|master_seed|repetition|500|month|actor_id",
                "master_seed": self.master_seed, "repetition": self.repetition,
                "policy_in_key": False}
