"""Research crew — market research, competitive analysis, and insights."""

from openfounder.crews.base import BaseCrew


class ResearchCrew(BaseCrew):
    crew_name = "research"
    prompt_file = "research_crew.md"
