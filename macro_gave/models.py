"Models et helpers de collecte."
from dataclasses import dataclass, field, asdict

CATEGORIES = ["croissance", "inflation", "energie", "bce", "geo"]

@dataclass
class DataPoint:
    category: str
    indicator: str
    value: float
    previous: float = None
    unit: str = ""
    source: str = ""
    published_date: str = ""
    extra: dict = field(default_factory=dict)
    available: bool = True
    def to_dict(self):
        return asdict(self)

@dataclass
class CollectorResult:
    points: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    source: str = ""
