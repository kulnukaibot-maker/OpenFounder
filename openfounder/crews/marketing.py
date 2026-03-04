"""Marketing crew — campaigns, content, and audience strategy."""

from openfounder.crews.base import BaseCrew


class MarketingCrew(BaseCrew):
    crew_name = "marketing"
    prompt_file = "marketing_crew.md"
