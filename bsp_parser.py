# bsp_parser.py
import re
import os
from bsp_data import UnitDef, MissionDef

# 1. SCANNED OBJECTS TO IGNORE (SCN Parsing)
IGNORED_SCN_CLASSES = {
    "PlaneCount", "MaxSquadSize", "Races", "Party", 
    "CommandType", "AttackMode", "FormationType", "MoveType",
    "MissionObjectives", "WeatherTypes", "mission_objectives",
    "RelationTypes", "NavpointType", "UnitType", "SpawnType",
    "WingCount", "AILevel", "LandingType", "InputId",
    "mission_objs", "CamState", "MusicType", "MovieType",
    "FlightDeckType", "HangarType", "GunType", "AmmoType"
}

# 2. ALWAYS INCLUDE THESE ENUMS
# These are the only specific enums we scan the SCN for.
ALWAYS_INCLUDE_ENUMS = {
    "PlaneClasses", "ShipClasses", "VehicleClasses"
}

class BSPParser:
    def __init__(self, game_root):
        self.root = game_root
        self.enums = {} 
        self.master_units = {} 
        self.master_unitlib = {} # Stores UnitLib content mapped by VehicleClass ID
        self.unitlib_header = "" # Stores the top part of UnitLib (Global vars)
        self.missions = [] 
        self.non_unit_lua = [] 
        self.always_include_lua = ""
        self.always_include_ids = set()

    def load_always_include(self, path):
        """Loads the AlwaysInclude_vehicleclasses.lua file."""
        print("Loading Always Include VehicleClasses...")
        try:
            if not os.path.exists(path):
                return "Warning: AlwaysInclude file not found"
            
            with open(path, 'r', encoding='latin-1') as f:
                self.always_include_lua = f.read()
                
            self.always_include_lua = re.sub(r'VehicleClass\s*=\s*\{\}', '', self.always_include_lua).strip()
            
            self.always_include_ids = set()
            pattern = re.compile(r'VehicleClass\s*\[\s*(\d+)\s*\]')
            for match in pattern.finditer(self.always_include_lua):
                self.always_include_ids.add(int(match.group(1)))
            
            print(f"Loaded AlwaysInclude ({len(self.always_include_ids)} units)")
        except Exception as e:
            return f"Error loading AlwaysInclude: {e}"
        return "Success"

    def load_global_enums(self, path):
        """Parses global.enums to map unit code names to IDs."""
        print("Loading Enums...")
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
            
            enum_pattern = re.compile(r'enum\s+(\w+)\s*\{([^}]+)\}', re.DOTALL)
            
            for match in enum_pattern.finditer(content):
                enum_body = match.group(2)
                entry_pattern = re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*(-?\d+)', enum_body)
                
                for name, num in entry_pattern:
                    self.enums[name] = int(num)
                    
        except Exception as e:
            return f"Error loading Global Enums: {e}"
        return "Success"

    def load_master_vehicle_classes(self, path):
        """Parses Master_vehicleclasses.lua."""
        print("Loading Master Vehicle Classes...")
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()

            first_match = re.search(r'VehicleClass\s*\[', content)
            if first_match:
                self.non_unit_lua.append(content[:first_match.start()])

            pattern = re.compile(r'VehicleClass\s*\[\s*(\d+)\s*\]\s*=')
            
            for match in pattern.finditer(content):
                unit_id = int(match.group(1))
                start_idx = match.end()
                
                # Find matching brace
                open_brace_idx = content.find('{', start_idx)
                if open_brace_idx == -1: continue 

                brace_count = 1
                current_idx = open_brace_idx + 1
                while brace_count > 0 and current_idx < len(content):
                    if content[current_idx] == '{': brace_count += 1
                    elif content[current_idx] == '}': brace_count -= 1
                    current_idx += 1
                
                block_content = content[open_brace_idx:current_idx] 
                full_lua = content[match.start():current_idx]

                code_match = re.search(r'\["Code"\]\s*=\s*"([^"]+)"', block_content)
                code = code_match.group(1) if code_match else "Unknown"
                
                self.master_units[unit_id] = UnitDef(unit_id, code, code, "Unknown", full_lua)

        except Exception as e:
            return f"Error parsing Master Vehicle Classes: {e}"
        return "Success"

    def load_master_unitlib(self, path):
        """Parses Master_unitlib.lua to associate data blocks with VehicleClass IDs."""
        print("Loading Master UnitLib...")
        try:
            if not os.path.exists(path):
                return "Warning: Master UnitLib not found"

            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()

            # Capture header (UnitLib = {})
            first_brace = content.find('{')
            if first_brace != -1:
                self.unitlib_header = content[:first_brace+1]
            else:
                self.unitlib_header = "UnitLib = {"

            # Regex to find table entries: ["SomeName"] = { ... }
            # We look for the ["VehicleClass"] = ID inside the block
            # This regex captures the key and the content inside the top-level braces
            # Note: This is a simplified parser. If UnitLib is very nested, it might need adjustment.
            
            # Strategy: Find start of an entry, then balance braces, then scan inside for VehicleClass ID
            iterator = re.finditer(r'\["([^"]+)"\]\s*=\s*\{', content)
            
            for match in iterator:
                key_name = match.group(1)
                start_idx = match.end() - 1 # Points to the opening {
                
                # Balance braces to find end of this block
                brace_count = 0
                current_idx = start_idx
                
                # Scan forward
                while current_idx < len(content):
                    char = content[current_idx]
                    if char == '{': brace_count += 1
                    elif char == '}': brace_count -= 1
                    
                    current_idx += 1
                    if brace_count == 0: break
                
                full_block = content[match.start():current_idx] + "," # Add comma for table list
                
                # Check for VehicleClass inside this block
                vc_match = re.search(r'\["VehicleClass"\]\s*=\s*(\d+)', full_block)
                if vc_match:
                    vc_id = int(vc_match.group(1))
                    
                    if vc_id not in self.master_unitlib:
                        self.master_unitlib[vc_id] = []
                    self.master_unitlib[vc_id].append(full_block)

            print(f"Loaded UnitLib data for {len(self.master_unitlib)} unique VehicleClass IDs")
            
        except Exception as e:
            return f"Error loading Master UnitLib: {e}"
        return "Success"

    def load_missions(self, path):
        """Loads missions from missiontree.lua"""
        print("Loading Mission Tree...")
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
            
            # Campaign
            group_pattern = re.compile(r'\["groupName"\]\s*=\s*"([^"]+)"(.*?)(?=\["groupName"\]|----\s*MULTIPLAYER|\Z)', re.DOTALL)
            mission_pattern = re.compile(r'\["id"\]\s*=\s*"([^"]+)".*?\["name"\]\s*=\s*"([^"]+)".*?\["sceneFile"\]\s*=\s*([^,]+),', re.DOTALL)

            for group_match in group_pattern.finditer(content):
                group_name = group_match.group(1)
                group_body = group_match.group(2)
                for m in mission_pattern.finditer(group_body):
                    m_id = m.group(1)
                    m_name = m.group(2)
                    raw_scene = m.group(3).replace('sceneFilePath..', '').replace('"', '').strip()
                    full_scene_path = os.path.join("universe", "Scenes", "missions", raw_scene.replace('/', os.sep))
                    self.missions.append(MissionDef(m_id, m_name, full_scene_path, group_name))

            # Multiplayer
            mp_section = re.search(r'----\s*MULTIPLAYER.*?MissionTree\s*\[\s*"multiMissionInfos"\s*\]\s*=\s*\{(.*?)\}(?=\s*----|\Z)', content, re.DOTALL)
            if mp_section:
                mp_iter = re.finditer(r'\{.*?\["id"\]\s*=\s*"([^"]+)".*?\["name"\]\s*=\s*"([^"]+)".*?\["sceneFile"\]\s*=\s*([^,]+),.*?\}', mp_section.group(1), re.DOTALL)
                for m in mp_iter:
                    m_id = m.group(1)
                    m_name = m.group(2)
                    raw_scene = m.group(3).replace('sceneFilePath..', '').replace('"', '').strip()
                    full_scene_path = os.path.join("universe", "Scenes", "missions", raw_scene.replace('/', os.sep))
                    self.missions.append(MissionDef(m_id, m_name, full_scene_path, "Multiplayer & Skirmish"))

        except Exception as e:
            return f"Error loading Mission Tree: {e}"
        return "Success"

    def _find_dependencies(self, lua_content):
        found_ids = set()
        potential_codes = re.findall(r'"([a-zA-Z0-9_]+)"', lua_content)
        for code in potential_codes:
            if code in self.enums:
                found_ids.add(self.enums[code])
        return found_ids

    def generate_mission_loader(self, mission_def):
        scn_full_path = os.path.join(self.root, mission_def.scn_path)
        if not os.path.exists(scn_full_path):
            return f"Error: SCN file not found at {scn_full_path}"

        required_ids = set()
        
        # --- 1. SCAN SCN ---
        try:
            with open(scn_full_path, 'r', encoding='latin-1') as f:
                content = f.read()
            
            # Matches: Type = E ShipClasses : CodeName
            matches = re.findall(r'Type\s*=\s*E\s+([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_-]+)', content)
            
            for class_type, code in matches:
                if class_type in IGNORED_SCN_CLASSES: continue 
                if class_type not in ALWAYS_INCLUDE_ENUMS: continue

                if code in self.enums:
                    unit_id = self.enums[code]
                    required_ids.add(unit_id)
        except Exception as e:
            return f"Error parsing SCN: {e}"

        # --- 2. DEPENDENCY CHECK ---
        ids_to_process = list(required_ids)
        processed_ids = set()
        
        while ids_to_process:
            current_id = ids_to_process.pop(0)
            if current_id in processed_ids: continue
            processed_ids.add(current_id)

            if current_id in self.master_units:
                unit_lua = self.master_units[current_id].lua_content
                dependencies = self._find_dependencies(unit_lua)
                
                for dep_id in dependencies:
                    if dep_id not in required_ids:
                        required_ids.add(dep_id)
                        ids_to_process.append(dep_id)

        # --- 3. WRITE VehicleClass.lua ---
        vc_lines = []
        vc_lines.append("VehicleClass = {}")
        vc_lines.append(f"-- Mission: {mission_def.name}")
        
        if self.always_include_lua:
            vc_lines.append("\n-- Always Include:")
            vc_lines.append(self.always_include_lua)
        
        vc_lines.append("\n-- Global Logic:")
        vc_lines.extend(self.non_unit_lua)
        
        vc_lines.append("\n-- Mission Units:")
        vc_write_count = 0
        
        for uid in sorted(required_ids):
            if uid <= 1: continue 
            if uid in self.always_include_ids: continue

            if uid in self.master_units:
                vc_lines.append(self.master_units[uid].lua_content)
                vc_write_count += 1

        vc_path = os.path.join(self.root, "scripts", "datatables", "autoload", "VehicleClass.lua")
        
        # --- 4. WRITE UnitLib.lua ---
        ul_lines = []
        # Use captured header or default
        ul_lines.append(self.unitlib_header if self.unitlib_header else "UnitLib = {")
        ul_lines.append(f"-- Filtered UnitLib for Mission: {mission_def.name}")
        
        ul_write_count = 0
        
        # Combine AlwaysInclude IDs + Mission Required IDs for UnitLib
        all_needed_ids = required_ids.union(self.always_include_ids)
        
        for uid in sorted(all_needed_ids):
            if uid in self.master_unitlib:
                # One ID might have multiple UnitLib entries
                for block in self.master_unitlib[uid]:
                    ul_lines.append(block)
                    ul_write_count += 1
        
        ul_lines.append("}") # Close the UnitLib table

        ul_path = os.path.join(self.root, "scripts", "datatables", "autoload", "UnitLib.lua")

        try:
            os.makedirs(os.path.dirname(vc_path), exist_ok=True)
            
            with open(vc_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(vc_lines))
                
            with open(ul_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(ul_lines))
                
        except Exception as e:
            return f"Error writing Output: {e}"

        return f"Success! Generated:\nVehicleClass: {vc_write_count} units\nUnitLib: {ul_write_count} entries"