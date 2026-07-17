from dataclasses import dataclass, field


@dataclass
class Evidence:
    field_name: str
    source_url: str
    quote: str
    fetch_method: str = "requests"
    pass_number: int = 1
    source_type: str = "general"


@dataclass
class FieldAnswer:
    value: str
    source_url: str = ""
    quote: str = ""
    certainty: str = "inferred"


@dataclass
class AppRecord:
    app_id: int
    name: str
    website: str
    fields: dict = field(default_factory=dict)

    def get(self, name, default="UNKNOWN"):
        ans = self.fields.get(name)
        return ans.value if ans else default


@dataclass
class ResearchPlan:
    app_id: int
    name: str
    website: str
    queries: list = field(default_factory=list)
    docs_guesses: list = field(default_factory=list)
