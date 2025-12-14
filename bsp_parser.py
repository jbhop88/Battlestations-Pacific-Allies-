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

MASTER_TREE_PREAMBLE = """DoFile(\"scripts/datatables/MultiGlobals.lua\")
function luaOverrideMultiLobbySettings(overrideTable)
    --overrideTabla formatuma meg kell egyezzen a MultiGlobals.lua MultiLobbySettings tabla szerkezetevel. Csak a MenuDIS parameter updatelodik!
    local uniqueMultiSettings
    if overrideTable == nil then
        return nil
    else
        if not type(overrideTable)=="table" then
            return nil
        else
            uniqueMultiSettings = {}
        end
    end

    for multiKey, multiValue in pairs (MultiLobbySettings) do
        uniqueMultiSettings[multiKey] = {}
        for paramKey, paramValue in pairs (multiValue) do
            uniqueMultiSettings[multiKey][paramKey] = {}
            local overrideUsed = false
            if overrideTable[multiKey] then
                if overrideTable[multiKey][paramKey] then
                    if overrideTable[multiKey][paramKey].MenuDIS ~= nil then
                        uniqueMultiSettings[multiKey][paramKey].MenuDIS = overrideTable[multiKey][paramKey].MenuDIS
                        overrideUsed = true
                    end
                end
            end
            if not overrideUsed and paramValue.MenuDIS ~= nil then
                uniqueMultiSettings[multiKey][paramKey].MenuDIS = paramValue.MenuDIS
            end
        end
    end

    return uniqueMultiSettings
end

---- SETTING GAMEMODE PARAMETERS -----

--DoFile(\"gamemode.lua\") -- Getting the gamemode from \"gamemode.lua\"

local sceneFilePath
--local sceneFilePathTraining

--[[if GameMode == 1 then -- Realistic

    sceneFilePath = \"universe/Scenes/realistic/missions/\"
    sceneFilePathTraining = \"universe/Scenes/realistic/\"

else -- Arcade]]

    sceneFilePath = \"universe/Scenes/missions/\"
    --sceneFilePathTraining = \"universe/Scenes/\"

--end

---- MISSION TREES START ----

MissionTree = {}
"""

class BSPParser:
    def __init__(self, game_root):
        self.root = game_root
        self.enums = {}
        self.master_units = {}
        self.master_unitlib = {} # Stores UnitLib content mapped by VehicleClass ID
        self.unitlib_groups = [] # Preserves group ordering and metadata from Master_unitlib
        self.unitlib_header = "" # Stores the top part of UnitLib (Global vars)
        self.missions = []
        self.non_unit_lua = []
        self.always_include_lua = ""
        self.always_include_ids = set()
        self.group_templates = {}
        self.multi_template = {"prefix": "", "suffix": ""}

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
                prefix = re.sub(r'VehicleClass\s*=\s*\{\}', '', content[:first_match.start()]).strip()
                if prefix:
                    self.non_unit_lua.append(prefix)

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

            self.master_unitlib = {}
            self.unitlib_groups = []

            # Capture header (UnitLib = {})
            first_brace = content.find('{')
            if first_brace != -1:
                self.unitlib_header = content[:first_brace+1]
            else:
                self.unitlib_header = "UnitLib = {"

            # Extract the full UnitLib body (inside the first top-level braces)
            def _find_matching_brace(start_idx: int) -> int:
                depth = 0
                for idx in range(start_idx, len(content)):
                    if content[idx] == '{':
                        depth += 1
                    elif content[idx] == '}':
                        depth -= 1
                    if depth == 0:
                        return idx
                return -1

            outer_close = _find_matching_brace(first_brace)
            if outer_close == -1:
                return "Error loading Master UnitLib: could not match UnitLib braces"

            body = content[first_brace + 1:outer_close]

            def _extract_blocks(segment: str):
                blocks = []
                idx = 0
                while idx < len(segment):
                    if segment[idx] == '{':
                        depth = 1
                        start = idx
                        idx += 1
                        while idx < len(segment) and depth > 0:
                            if segment[idx] == '{':
                                depth += 1
                            elif segment[idx] == '}':
                                depth -= 1
                            idx += 1
                        blocks.append(segment[start:idx])
                    else:
                        idx += 1
                return blocks

            group_blocks = _extract_blocks(body)

            for group_block in group_blocks:
                # Separate header (GroupName/comments) from unit entries
                group_body = group_block[1:-1]  # remove outer braces
                entry_blocks = _extract_blocks(group_body)

                header_text = ""
                if entry_blocks:
                    first_entry = entry_blocks[0]
                    first_idx = group_body.find(first_entry)
                    header_text = group_body[:first_idx].strip()

                stored_entries = []
                for entry in entry_blocks:
                    vc_match = re.search(r'\["VehicleClass"\]\s*=\s*(\d+)', entry)
                    if not vc_match:
                        continue
                    vc_id = int(vc_match.group(1))
                    stored_entries.append((vc_id, entry))

                    if vc_id not in self.master_unitlib:
                        self.master_unitlib[vc_id] = []
                    self.master_unitlib[vc_id].append(entry)

                if stored_entries:
                    self.unitlib_groups.append({
                        "header": header_text,
                        "entries": stored_entries,
                    })

            print(f"Loaded UnitLib data for {len(self.master_unitlib)} unique VehicleClass IDs")

        except Exception as e:
            return f"Error loading Master UnitLib: {e}"
        return "Success"

    def _extract_block(self, content: str, start_idx: int) -> str:
        """Extracts a brace-delimited block starting at start_idx."""
        if start_idx < 0 or start_idx >= len(content) or content[start_idx] != '{':
            return ""

        depth = 1
        idx = start_idx + 1
        while idx < len(content) and depth > 0:
            if content[idx] == '{':
                depth += 1
            elif content[idx] == '}':
                depth -= 1
            idx += 1
        return content[start_idx:idx]

    def _extract_blocks(self, segment: str):
        blocks = []
        idx = 0
        while idx < len(segment):
            if segment[idx] == '{':
                depth = 1
                start = idx
                idx += 1
                while idx < len(segment) and depth > 0:
                    if segment[idx] == '{':
                        depth += 1
                    elif segment[idx] == '}':
                        depth -= 1
                    idx += 1
                blocks.append(segment[start:idx])
            else:
                idx += 1
        return blocks

    def load_missions(self, path):
        """Loads missions from missiontree.lua"""
        print("Loading Mission Tree...")
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()

            self.group_templates = {}
            self.missions = []

            search_idx = 0
            while True:
                group_match = re.search(r'\["groupName"\]\s*=\s*"([^"]+)"', content[search_idx:])
                if not group_match:
                    break

                absolute_start = search_idx + group_match.start()
                group_name = group_match.group(1)
                brace_start = content.rfind('{', 0, absolute_start)
                group_block = self._extract_block(content, brace_start)
                search_idx = brace_start + len(group_block)

                missions_key_idx = group_block.find('["missions"]')
                if missions_key_idx == -1:
                    continue

                missions_block_start = group_block.find('{', missions_key_idx)
                missions_block = self._extract_block(group_block, missions_block_start)

                prefix = group_block[:missions_block_start + 1]
                suffix = group_block[missions_block_start + len(missions_block):]
                self.group_templates[group_name] = {"prefix": prefix, "suffix": suffix}

                for mission_block in self._extract_blocks(missions_block[1:-1]):
                    id_match = re.search(r'\["id"\]\s*=\s*"([^"]+)"', mission_block)
                    name_match = re.search(r'\["name"\]\s*=\s*"([^"]+)"', mission_block)
                    scene_match = re.search(r'\["sceneFile"\]\s*=\s*([^,}]+)', mission_block)

                    if not (id_match and name_match and scene_match):
                        continue

                    m_id = id_match.group(1)
                    m_name = name_match.group(1)
                    raw_scene = scene_match.group(1).replace('sceneFilePath..', '').replace('"', '').strip()
                    full_scene_path = os.path.join("universe", "Scenes", "missions", raw_scene.replace('/', os.sep))
                    self.missions.append(MissionDef(m_id, m_name, full_scene_path, group_name, mission_block))

            multi_section_match = re.search(r'MissionTree\s*\[\s*"multiMissionInfos"\s*\]\s*=\s*\{', content)
            if multi_section_match:
                multi_block_start = content.find('{', multi_section_match.end() - 1)
                multi_block = self._extract_block(content, multi_block_start)
                self.multi_template = {
                    "prefix": "MissionTree[\"multiMissionInfos\"] = " + multi_block[:1],
                    "suffix": multi_block[len(multi_block) - 1 :],
                }

                for mission_block in self._extract_blocks(multi_block[1:-1]):
                    id_match = re.search(r'\["id"\]\s*=\s*"([^"]+)"', mission_block)
                    name_match = re.search(r'\["name"\]\s*=\s*"([^"]+)"', mission_block)
                    scene_match = re.search(r'\["sceneFile"\]\s*=\s*([^,}]+)', mission_block)
                    if not (id_match and name_match and scene_match):
                        continue

                    m_id = id_match.group(1)
                    m_name = name_match.group(1)
                    raw_scene = scene_match.group(1).replace('sceneFilePath..', '').replace('"', '').strip()
                    full_scene_path = os.path.join("universe", "Scenes", "missions", raw_scene.replace('/', os.sep))
                    self.missions.append(MissionDef(m_id, m_name, full_scene_path, "Multiplayer & Skirmish", mission_block))

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

    def _collect_required_ids(self, mission_def: MissionDef):
        scn_full_path = os.path.join(self.root, mission_def.scn_path)
        if not os.path.exists(scn_full_path):
            return None, f"Error: SCN file not found at {scn_full_path}"

        required_ids = set()

        try:
            with open(scn_full_path, 'r', encoding='latin-1') as f:
                content = f.read()

            matches = re.findall(r'Type\s*=\s*E\s+([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_-]+)', content)

            for class_type, code in matches:
                if class_type in IGNORED_SCN_CLASSES:
                    continue
                if class_type not in ALWAYS_INCLUDE_ENUMS:
                    continue

                if code in self.enums:
                    unit_id = self.enums[code]
                    required_ids.add(unit_id)
        except Exception as e:
            return None, f"Error parsing SCN: {e}"

        ids_to_process = list(required_ids)
        processed_ids = set()

        while ids_to_process:
            current_id = ids_to_process.pop(0)
            if current_id in processed_ids:
                continue
            processed_ids.add(current_id)

            if current_id in self.master_units:
                unit_lua = self.master_units[current_id].lua_content
                dependencies = self._find_dependencies(unit_lua)

                for dep_id in dependencies:
                    if dep_id not in required_ids:
                        required_ids.add(dep_id)
                        ids_to_process.append(dep_id)

        return required_ids, None

    def generate_mission_loader(self, mission_def):
        return self.generate_for_missions([mission_def])

    def generate_for_missions(self, mission_list):
        if not mission_list:
            return "Error: No missions provided"

        combined_ids = set()
        for mission_def in mission_list:
            mission_ids, err = self._collect_required_ids(mission_def)
            if err:
                return err
            combined_ids.update(mission_ids)

        mission_label = ", ".join(m.name for m in mission_list)

        vc_lines = []
        vc_lines.append("VehicleClass = {}")
        vc_lines.append(f"-- Mission: {mission_label}")

        if self.always_include_lua:
            vc_lines.append("\n-- Always Include:")
            vc_lines.append(self.always_include_lua)

        vc_lines.append("\n-- Global Logic:")
        vc_lines.extend(self.non_unit_lua)

        vc_lines.append("\n-- Mission Units:")
        vc_write_count = 0

        for uid in sorted(combined_ids):
            if uid <= 1:
                continue
            if uid in self.always_include_ids:
                continue

            if uid in self.master_units:
                vc_lines.append(self.master_units[uid].lua_content)
                vc_write_count += 1

        vc_path = os.path.join(self.root, "scripts", "datatables", "autoload", "VehicleClass.lua")
        
        # --- 4. WRITE UnitLib.lua ---
        ul_lines = []
        # Use captured header or default
        ul_lines.append(self.unitlib_header.strip() if self.unitlib_header else "UnitLib = {")
        ul_lines.append(f"-- Filtered UnitLib for Mission: {mission_label}")

        ul_write_count = 0

        # Combine AlwaysInclude IDs + Mission Required IDs for UnitLib
        all_needed_ids = combined_ids.union(self.always_include_ids)

        for group in self.unitlib_groups:
            filtered_entries = [(vc_id, block) for vc_id, block in group["entries"] if vc_id in all_needed_ids]
            if not filtered_entries:
                continue

            ul_lines.append("{")
            if group["header"]:
                ul_lines.append(group["header"].rstrip())

            for idx, (_, entry) in enumerate(filtered_entries):
                entry_clean = entry.strip()
                needs_comma = not entry_clean.rstrip().endswith(",")
                suffix = "," if needs_comma else ""
                ul_lines.append(f"{entry_clean}{suffix}")
                if idx < len(filtered_entries) - 1:
                    ul_lines.append("")

            ul_lines.append("},")
            ul_write_count += len(filtered_entries)

        ul_lines.append("}") # Close the UnitLib table

        ul_path = os.path.join(self.root, "scripts", "datatables", "UnitLib.lua")

        mission_tree_content = self._build_mission_tree_content(mission_list)
        mission_tree_path = os.path.join(self.root, "scripts", "datatables", "master_missiontree.lua")

        try:
            os.makedirs(os.path.dirname(vc_path), exist_ok=True)
            os.makedirs(os.path.dirname(ul_path), exist_ok=True)

            with open(vc_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(vc_lines))

            with open(ul_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(ul_lines))

            with open(mission_tree_path, 'w', encoding='utf-8') as f:
                f.write(mission_tree_content)

        except Exception as e:
            return f"Error writing Output: {e}"

        return (
            "Success! Generated:\n"
            f"VehicleClass: {vc_write_count} units\n"
            f"UnitLib: {ul_write_count} entries\n"
            f"master_missiontree.lua with {len(mission_list)} selected mission(s)"
        )

    def _build_mission_tree_content(self, mission_list):
        lines = [MASTER_TREE_PREAMBLE.strip(), ""]

        campaign_groups = {}
        multiplayer_missions = []

        for mission in mission_list:
            if mission.group == "Multiplayer & Skirmish":
                multiplayer_missions.append(mission)
            else:
                campaign_groups.setdefault(mission.group, []).append(mission)

        lines.append('MissionTree["missionGroups"] = {')
        if campaign_groups:
            for group_name, missions in campaign_groups.items():
                template = self.group_templates.get(group_name, {"prefix": "{", "suffix": "},"})
                lines.append(template["prefix"].rstrip())

                mission_blocks = []
                for mission in missions:
                    block = mission.raw_block.strip()
                    if not block:
                        rel_scene = mission.scn_path.replace(os.path.join("universe", "Scenes") + os.sep, "")
                        block = (
                            "{"
                            f"[\"id\"] = \"{mission.id}\"," 
                            f" [\"name\"] = \"{mission.name}\"," 
                            f" [\"sceneFile\"] = sceneFilePath..\"{rel_scene.replace(os.sep, '/')}\""
                            "}"
                        )
                    if not block.rstrip().endswith(','):
                        block = block + ','
                    mission_blocks.append(block)

                lines.append("\n\n".join(mission_blocks))
                lines.append(template["suffix"].lstrip())
        lines.append("}")

        lines.append("")
        lines.append('MissionTree["multiMissionInfos"] = {')
        if multiplayer_missions:
            for mission in multiplayer_missions:
                block = mission.raw_block.strip()
                if not block.rstrip().endswith(','):
                    block = block + ','
                lines.append(block)
        lines.append("}")

        return "\n".join(lines)
