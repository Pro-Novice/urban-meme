from enum import Enum

class OfficerRole(Enum):
    AGRICULTURE_OFFICER = 0
    ASSISTANT_AGRICULTURE_OFFICER = 1
    ASSISTANT_DIRECTOR = 2
    DEPUTY_DIRECTOR = 3
    JOINT_DIRECTOR = 4
    JOINT_DIRECTOR_INPUT = 5

    @staticmethod
    def from_string(role_str: str):
        normalized = role_str.strip().lower().replace(" ", "_")
        mapping = {
            "agriculture_officer": OfficerRole.AGRICULTURE_OFFICER,
            "assistant_agriculture_officer": OfficerRole.ASSISTANT_AGRICULTURE_OFFICER,
            "assistant_director": OfficerRole.ASSISTANT_DIRECTOR,
            "deputy_director": OfficerRole.DEPUTY_DIRECTOR,
            "joint_director": OfficerRole.JOINT_DIRECTOR,
            "joint_director_input": OfficerRole.JOINT_DIRECTOR_INPUT,
        }
        if normalized not in mapping:
            raise ValueError(f"Invalid officer role string: '{role_str}'")
        return mapping[normalized]

class DivisionEnum(Enum):
    AJMER = 0
    BHARATPUR = 1
    BIKANER = 2
    JAIPUR = 3
    JODHPUR = 4
    KOTA = 5
    UDAIPUR = 6

    @staticmethod
    def from_string(div_str: str):
        normalized = div_str.strip().lower().replace(" ", "_")
        mapping = {
            "ajmer": "AJMER",
            "bharatpur": "BHARATPUR",
            "bikaner": "BIKANER",
            "jaipur": "JAIPUR",
            "jodhpur": "JODHPUR",
            "kota": "KOTA",
            "udaipur": "UDAIPUR",
        }
        if normalized not in mapping:
            raise ValueError(f"Invalid division string: '{div_str}'")
        return mapping[normalized]

# class CityEnum(Enum):
#     # Ajmer Division
#     AJMER = 0
#     BEAWAR = 1
#     BHILWARA = 2
#     DIDWANA_KUCHAMAN = 3
#     NAGAUR = 4
#     TONK = 5
#
#     # Bharatpur Division
#     BHARATPUR = 6
#     DEEG = 7
#     DHOLPUR = 8
#     KARAULI = 9
#     SAWAI_MADHOPUR = 10
#
#     # Bikaner Division
#     BIKANER = 11
#     CHURU = 12
#     HANUMANGARH = 13
#     SRI_GANGANAGAR = 14
#
#     # Jaipur Division
#     ALWAR = 15
#     DAUSA = 16
#     JAIPUR = 17
#     JHUNJHUNU = 18
#     KHAIRTHAL_TIARA = 19
#     KOTPUTLI_BEHROR = 20
#     SIKAR = 21
#
#     # Jodhpur Division
#     BALOTRA = 22
#     BARMER = 23
#     JAISALMER = 24
#     JALORE = 25
#     JODHPUR = 26
#     PALI = 27
#     PHALODI = 28
#     SIROHI = 29
#
#     # Kota Division
#     BARAN = 30
#     BUNDI = 31
#     JHALAWAR = 32
#     KOTA = 33
#
#     # Udaipur Division
#     BANSWARA = 34
#     CHITTORGARH = 35
#     DUNGARPUR = 36
#     PRATAPGARH = 37
#     RAJSAMAND = 38
#     SALUMBAR = 39
#
#     @staticmethod
#     def from_string(city_str: str):
#         normalized = city_str.strip().lower().replace(" ", "_").replace("-", "_")
#         mapping = {c.name.lower(): c for c in CityEnum}
#         if normalized not in mapping:
#             raise ValueError(f"Invalid city string: '{city_str}'")
#         return mapping[normalized]