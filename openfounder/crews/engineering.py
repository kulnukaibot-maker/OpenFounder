"""Engineering crew — technical planning and code execution."""

from openfounder.crews.base import BaseCrew


class EngineeringCrew(BaseCrew):
    crew_name = "engineering"
    prompt_file = "engineering_crew.md"
