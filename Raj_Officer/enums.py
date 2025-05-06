from enum import Enum

# Enums for Department Names
class Department(Enum):
    """Enum for department names in the organization."""
    NONE = 0
    AGRICULTURE = 1
    SUBSIDY = 2
    SEED_LICENCE = 3
    QUALITY_CONTROL = 4
    SALES = 5
    LEGAL = 6

# Enums for Officer Designations
class Designation(Enum):
    """Enum for officer designations in the organization."""
    NONE = 0
    AGRICULTURE_OFFICER = 1
    DISTRICT_COLLECTOR = 2
    SEED_CERTIFICATION_OFFICER = 3
    SUBSIDY_APPROVAL_OFFICER = 4
    QUALITY_CONTROL_OFFICER = 5
    ADMINISTRATOR = 6

# Enums for Officer Roles
class OfficerRoles(Enum):
    """Enum for officer roles within the agriculture and district offices."""
    NONE = 0
    ASSISTANT_AGRICULTURE_OFFICER = 1
    AGRICULTURE_OFFICER = 2
    DEPUTY_AGRICULTURE_OFFICER = 3
    ASSISTANT_DISTRICT_COLLECTOR = 4
    DISTRICT_COLLECTOR = 5
    DEPUTY_DISTRICT_COLLECTOR = 6
    ASSISTANT_SEED_CERTIFICATION_OFFICER = 7
    SEED_CERTIFICATION_OFFICER = 8
    DEPUTY_SEED_CERTIFICATION_OFFICER = 9
    ASSISTANT_SUBSIDY_APPROVAL_OFFICER = 10
    SUBSIDY_APPROVAL_OFFICER = 11
    DEPUTY_SUBSIDY_APPROVAL_OFFICER = 12
    ASSISTANT_QUALITY_CONTROL_OFFICER = 13
    QUALITY_CONTROL_OFFICER = 14
    DEPUTY_QUALITY_CONTROL_OFFICER = 15
