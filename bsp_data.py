# bsp_data.py
import os

class MissionDef:
    def __init__(self, mission_id, name, scn_path, group="Unknown"):
        self.id = mission_id
        self.name = name
        self.scn_path = scn_path
        self.group = group

class UnitDef:
    def __init__(self, unit_id, name, code, unit_type, lua_content):
        self.unit_id = unit_id
        self.name = name
        self.code = code
        self.unit_type = unit_type # Stores "Ship", "LandFort", etc.
        self.lua_content = lua_content

# Common paths relative to the Game Root
PATH_MASTER_LUA = os.path.join("scripts", "datatables", "autoload", "Master_vehicleclasses.lua")
PATH_MISSION_TREE = os.path.join("scripts", "datatables", "missiontree.lua")
PATH_GLOBAL_ENUMS = os.path.join("universe", "library", "global.enums")
PATH_ALWAYS_INCLUDE = os.path.join("scripts", "datatables", "autoload", "AlwaysInclude_vehicleclasses.lua")