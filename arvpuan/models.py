from dataclasses import dataclass
from typing import Optional


@dataclass
class CardResult:
    card_data: str = ""
    success: bool = False
    error: Optional[str] = None
    card: str = ""
    full_card: str = ""
    expiry: str = ""
    month: str = ""
    year: str = ""
    cvv: str = ""
    points: float = 0.0
    formatted: str = ""
    has_points: bool = False
    bank: str = ""
    program: str = ""
    saved_at: Optional[str] = None
    used: bool = False

    @property
    def is_live(self) -> bool:
        return self.success and self.has_points

    @property
    def is_dead(self) -> bool:
        return self.success and not self.has_points

    @property
    def is_error(self) -> bool:
        return not self.success

    def __str__(self) -> str:
        if self.is_live:
            return "[LIVE] " + self.card + " | " + self.formatted + " | " + self.bank
        if self.is_dead:
            return "[DEAD] " + self.card
        return "[ERR]  " + (self.card or self.card_data[:20]) + " | " + str(self.error)

    def to_dict(self) -> dict:
        return {
            "card_data":  self.card_data,
            "success":    self.success,
            "error":      self.error,
            "card":       self.card,
            "full_card":  self.full_card,
            "expiry":     self.expiry,
            "month":      self.month,
            "year":       self.year,
            "cvv":        self.cvv,
            "points":     self.points,
            "formatted":  self.formatted,
            "has_points": self.has_points,
            "bank":       self.bank,
            "program":    self.program,
            "saved_at":   self.saved_at,
            "used":       self.used,
        }
