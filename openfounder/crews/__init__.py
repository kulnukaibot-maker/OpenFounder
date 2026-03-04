from openfounder.crews.base import BaseCrew, run_crew
from openfounder.crews.engineering import EngineeringCrew
from openfounder.crews.marketing import MarketingCrew
from openfounder.crews.research import ResearchCrew

CREWS = {
    "engineering": EngineeringCrew,
    "marketing": MarketingCrew,
    "research": ResearchCrew,
}

__all__ = ["BaseCrew", "run_crew", "CREWS", "EngineeringCrew", "MarketingCrew", "ResearchCrew"]
