import os
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import logging
import re

logging.basicConfig(
    level=logging.ERROR,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# TODO: Figure out why the armour bases are not generating blocks correctly, without breaking the other things that are working.

# Constants from existing poe2filter.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "bases")
FILTER_DIR = SCRIPT_DIR
FILTER_BASE = "filterbase.filter"
FILTER_TEMP = "filter.txt"
FILTER_OUTPUT = "filter.filter"
AREA_LEVEL_MARKER = "Area Level"
REQUIRES_MARKER = "Requires:"
LEVEL_MARKER = "Level"
PHYSICAL_DAMAGE_MARKER = "Physical Damage:"
CRIT_CHANCE_MARKER = "Critical Hit Chance:"
ATTACKS_PER_SECOND_MARKER = "Attacks per Second:"
WEAPON_RANGE_MARKER = "Weapon Range:"
SPIRIT_MARKER = "Spirit:"
GRANTS_SKILL_MARKER = "Grants Skill:"

class BaseItem:
    def __init__(self, name: str, area_level: str, filepath: Optional[str] = None):
        self.name = name
        self.area_level = area_level
        self._filepath = filepath
        self.level_req: Optional[int] = None
        self.attribute_reqs: Dict[str, int] = {}
        
    @property
    def is_endgame(self) -> bool:
        return "Expert" in self.name or self.area_level.endswith("+")
        
    @property
    def is_advanced(self) -> bool:
        return "Advanced" in self.name

    def validate(self) -> bool:
        """Validate that required fields are set."""
        return bool(self.name and self.area_level)

    @property
    def category(self) -> str:
        """Get the item category based on directory structure."""
        if not self._filepath:
            return "unknown"
        return self._filepath.split('bases/')[-1].split('/')[0]

    def parse_area_level(self, area_level: str) -> Tuple[int, Optional[int]]:
        """Parse area level string into min and max levels."""
        # Remove "Area Level " prefix if present
        area_level = area_level.replace("Area Level ", "")
        
        # Handle endgame case with "+"
        if area_level.endswith("+"):
            min_level = int(area_level.rstrip("+"))
            return min_level, None
            
        # Handle range case with "-"
        if "-" in area_level:
            min_level, max_level = map(int, area_level.split("-"))
            return min_level, max_level
            
        # Handle single number case
        return int(area_level), None

    @property
    def min_area_level(self) -> int:
        return self.parse_area_level(self.area_level)[0]

    @property
    def max_area_level(self) -> Optional[int]:
        """Get the maximum area level if it exists."""
        if self.is_endgame:
            return None
        return self.parse_area_level(self.area_level)[1]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseItem):
            return NotImplemented
        return self.name == other.name and self.area_level == other.area_level

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, BaseItem):
            return NotImplemented
        return self.min_area_level < other.min_area_level

    def __hash__(self) -> int:
        return hash((self.name, self.area_level))

class DefenseItem(BaseItem):
    def __init__(self, name: str, area_level: str, filepath: Optional[str] = None):
        super().__init__(name, area_level, filepath)
        self.armour: int = 0
        self.evasion: int = 0
        self.energy_shield: int = 0
        self.block_chance: Optional[int] = None
        
    def validate(self) -> bool:
        """Validate that at least one defense stat is set."""
        return super().validate() and any([
            self.armour > 0,
            self.evasion > 0,
            self.energy_shield > 0
        ])

class WeaponItem(BaseItem):
    def __init__(self, name: str, area_level: str, filepath: Optional[str] = None):
        super().__init__(name, area_level, filepath)
        self.physical_damage_min: int = 0
        self.physical_damage_max: int = 0
        self.crit_chance: float = 0.0
        self.attacks_per_second: float = 0.0
        self.weapon_range: float = 0.0
        self.tier = None

    def validate(self) -> bool:
        """Validate that required weapon stats are set."""
        return super().validate() and all([
            self.physical_damage_min >= 0,
            self.physical_damage_max > 0,
            self.crit_chance > 0,
            self.attacks_per_second > 0
        ])

class SkillWeaponItem(BaseItem):
    def __init__(self, name: str, area_level: str, filepath: Optional[str] = None):
        super().__init__(name, area_level, filepath)
        self.spirit: Optional[int] = None
        self.granted_skill: Optional[str] = None

    def validate(self) -> bool:
        """Validate that skill weapon has required properties."""
        return super().validate() and self.granted_skill is not None

class CrossbowItem(WeaponItem):
    def __init__(self, name: str, area_level: str):
        super().__init__(name, area_level)
        self.reload_time: float = 0.0

    def validate(self) -> bool:
        return super().validate() and self.reload_time > 0

class QuiverItem(BaseItem):
    def __init__(self, name: str, area_level: str, filepath: Optional[str] = None):
        super().__init__(name, area_level, filepath)
        self.implicit_effect: Optional[str] = None

    def validate(self) -> bool:
        """Validate that quiver has required properties."""
        return super().validate()

class FilterSettings:
    def __init__(self, settings_file):
        self.show_settings = {}
        self.styles = {}
        logger.debug(f"Initializing FilterSettings with file: {settings_file}")
        self.parse_settings_file(settings_file)
        
    def parse_settings_file(self, settings_file):
        """Parse settings from txt file"""
        current_section = None
        current_style = None
        
        with open(settings_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                    
                # Parse show/hide settings
                if "=" in line and ":" not in line:  # Added ": not in line" to avoid matching style lines
                    key, value = [x.strip() for x in line.split("=", 1)]
                    value = value.split('#')[0].strip()
                    self.show_settings[key] = value.lower() == 'true'
                    
                # Check for style section - strip quotes and "{" from style name
                elif line.endswith("{"):
                    current_style = line.split("{")[0].strip().strip('"').strip(':').strip()
                    logger.debug(f"Found style section: {current_style}")
                    self.styles[current_style] = {}
                    continue
                    
                # Check for style closing
                elif line.startswith("}"):
                    current_style = None
                    continue
                    
                # Parse style settings
                elif current_style is not None and ":" in line:
                    if line.strip().startswith("#"):  # Skip comments inside style blocks
                        continue
                    key, value = [x.strip().strip('"').strip(',') for x in line.split(":", 1)]
                    self.styles[current_style][key] = value
                    
        logger.debug("Parsed styles:")
        for style, settings in self.styles.items():
            logger.debug(f"Style: {style}")
            logger.debug(f"Settings: {settings}")

class FilterBlockGenerator:
    def __init__(self, settings: FilterSettings):
        self.settings = settings

    def _get_defense_type(self, item: DefenseItem) -> str:
        """Get the defense type string for an item."""
        has_armour = item.armour > 0
        has_evasion = item.evasion > 0
        has_es = item.energy_shield > 0
        
        if has_armour and has_evasion:
            return "ARMOUR/EVASION"
        elif has_armour and has_es:
            return "ARMOUR/ES"
        elif has_evasion and has_es:
            return "EVASION/ES"
        elif has_armour:
            return "ARMOUR"
        elif has_evasion:
            return "EVASION"
        elif has_es:
            return "ES"
        return ""

    def _get_item_class(self, item: BaseItem) -> str:
        """Get the item class based on filepath."""
        if not item._filepath:
            return "UNKNOWN"
        
        parts = item._filepath.split('/')
        if len(parts) < 2:
            return "UNKNOWN"
        
        # For weapons, use the specific weapon type from the filename
        if 'martial weapons' in item._filepath.lower() or 'skill-based weapons' in item._filepath.lower():
            # Get filename without extension
            weapon_type = parts[-1].replace('.txt', '').upper()
            # Handle special cases
            if weapon_type == "ONEHANDMACES":
                return "ONE HAND MACES"
            elif weapon_type == "TWOHANDMACES":
                return "TWO HAND MACES"
            return weapon_type
        
        # For other items, use the directory name
        return parts[-2].upper()

    def _create_header(self, item: BaseItem) -> str:
        """Create the descriptive header comment."""
        if isinstance(item, SkillWeaponItem) and item.granted_skill:
            # Special case for Purity Sceptres
            if item.name == "Shrine Sceptre" and "Purity" in item.granted_skill:
                return "# PURITY SCEPTRES"
            
            weapon_type = (
                'WANDS' if 'wands' in item._filepath.lower() else
                'STAVES' if 'staves' in item._filepath.lower() else
                'SCEPTRES' if 'sceptres' in item._filepath.lower() else
                'UNKNOWN'
            )
            return f"# {item.granted_skill.upper()} {weapon_type}"
        
        if 'quivers' in item._filepath.lower():
            return f"# {item.name}"  # Use the quiver's name as the header
        
        # Original header logic for other items...
        parts = []
        if item.is_endgame:
            parts.append("ENDGAME")
            if "Expert" in item.name:
                parts.append("T1")
            elif "Advanced" in item.name:
                parts.append("T2")
        else:
            parts.append("LEVELING")
            
        # Add defense type for defense items
        if isinstance(item, DefenseItem):
            defense_type = self._get_defense_type(item)
            if defense_type:
                parts.append(defense_type)
                
        # Add item class
        parts.append(self._get_item_class(item))
        
        # Add area level - use the original area_level string from the item
        parts.append(f"({item.area_level})")
        
        return f"# {' '.join(parts)}"

    def create_block(self, item: BaseItem, show: bool = True, style: Optional[str] = None) -> str:
        """Create a filter block for an item."""
        lines = []
        
        # Add header comment
        lines.append(self._create_header(item))
        
        # Add show/hide line
        lines.append("Show" if show else "Hide")
        
        # Add base type
        lines.append(f'BaseType "{item.name}"')
        
        # Add area level condition for leveling items
        if not item.is_endgame and item.max_area_level:
            lines.append(f"AreaLevel <= {item.max_area_level}")
        
        # Add style if showing
        if show:
            if style:
                style_dict = self.settings.styles.get(style, {})
            else:
                style_dict = self.settings.get_style_for_item(item)
            lines.extend(self._format_style(style_dict))
        
        # Add blank line at end of block
        lines.append("")
        
        return "\n".join(lines) + "\n"

    def create_consolidated_block(self, items: List[BaseItem], show: bool = True, style: Optional[str] = None) -> str:
        """Create a filter block for multiple items."""
        if not items:
            return ""
            
        lines = []
        item = items[0]  # Use first item for header and style
        
        # Add header comment
        lines.append(self._create_header(item))
        
        # Add show/hide line
        lines.append("Show" if show else "Hide")
        
        # Add base types
        base_types = [f'"{item.name}"' for item in items]
        lines.append(f'BaseType {" ".join(base_types)}')
        
        # Add area level condition for leveling items
        if not item.is_endgame and item.max_area_level:
            lines.append(f"AreaLevel <= {item.max_area_level}")
        
        # Add style if showing
        if show:
            if style:
                style_dict = self.settings.styles.get(style, {})
            else:
                style_dict = self.settings.get_style_for_item(item)
            lines.extend(self._format_style(style_dict))
        
        # Add blank line at end of block
        lines.append("")
        
        return "\n".join(lines) + "\n"

    def _format_style(self, style: Dict[str, str]) -> List[str]:
        """Format style dictionary into filter syntax lines."""
        lines = []
        
        # Convert size string to integer
        size_map = {
            "Large": "0",
            "Medium": "1",
            "Small": "2"
        }
        
        # Handle minimap icon properties together
        if "MinimapIconSize" in style:
            size = size_map.get(style["MinimapIconSize"], "0")
            color = style.get("MinimapIconColour", "White")
            shape = style.get("MinimapIconShape", "Circle")
            lines.append(f"MinimapIcon {size} {color} {shape}")
            
            # Remove these keys so they're not processed again
            style.pop("MinimapIconSize", None)
            style.pop("MinimapIconColour", None)
            style.pop("MinimapIconShape", None)
        
        # Add remaining style properties
        for key, value in style.items():
            lines.append(f"{key} {value}")
        
        return lines

class DefenseBaseParser:
    def __init__(self):
        self.area_level_pattern = r'Area Level (\d+)(?:-(\d+)|\+)'
        
    def parse_area_level(self, first_line):
        """Extract area level info and determine if leveling/endgame"""
        match = re.search(self.area_level_pattern, first_line)
        if not match:
            return None, None, None
            
        min_level = int(match.group(1))
        if match.group(2):  # Has range (e.g. 1-4)
            max_level = int(match.group(2))
            is_endgame = False
        else:  # Has + (e.g. 63+)
            max_level = None
            is_endgame = True
            
        return min_level, max_level, is_endgame
        
    def get_defense_values(self, lines):
        """Extract armor/evasion/es values"""
        values = {}
        for line in lines:
            if "Armour:" in line:
                values["armour"] = int(line.split(":")[1].strip())
            elif "Evasion Rating:" in line:
                values["evasion"] = int(line.split(":")[1].strip())
            elif "Energy Shield:" in line:
                values["es"] = int(line.split(":")[1].strip())
        return values

def parse_item_file(filepath: str) -> List[BaseItem]:
    """Parse a single item file and return a list of items."""
    items = []
    current_item = None
    
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Start new item when we see a name with area level
            if '(Area Level' in line:
                if current_item and current_item.validate():
                    items.append(current_item)
                
                # Extract name and area level
                name = line.split(' (Area Level')[0].strip()
                area_level = line.split('(Area Level ')[1].split(')')[0].strip()
                
                # Handle different weapon types
                if 'martial weapons' in filepath.lower():
                    current_item = WeaponItem(name, area_level)
                    current_item._filepath = filepath
                    # Look ahead for Tier if this is an endgame item
                    if "+" in area_level and i + 1 < len(lines) and "Tier" in lines[i + 1]:
                        current_item.tier = int(lines[i + 1].split("Tier")[1].strip())
                        i += 1  # Skip the tier line since we've processed it
                elif 'quivers' in filepath.lower():
                    current_item = QuiverItem(name, area_level, filepath)
                elif any(x in filepath.lower() for x in ['wands', 'staves', 'sceptres']):
                    current_item = SkillWeaponItem(name, area_level, filepath)
                else:
                    current_item = BaseItem(name, area_level, filepath)
                    current_item._filepath = filepath
            
            # Parse weapon properties
            elif current_item and isinstance(current_item, WeaponItem):
                if "Physical Damage:" in line:
                    damage = line.split(":")[1].strip()
                    min_dmg, max_dmg = map(int, damage.split("-"))
                    current_item.physical_damage_min = min_dmg
                    current_item.physical_damage_max = max_dmg
                elif "Critical Hit Chance:" in line:
                    crit = line.split(":")[1].strip().rstrip("%")
                    current_item.crit_chance = float(crit)
                elif "Attacks per Second:" in line:
                    aps = line.split(":")[1].strip()
                    current_item.attacks_per_second = float(aps)
                elif "Reload Time:" in line and isinstance(current_item, CrossbowItem):
                    reload = line.split(":")[1].strip()
                    current_item.reload_time = float(reload)
            
            i += 1
            
    # Add final item if valid
    if current_item and current_item.validate():
        items.append(current_item)
        
    return items

@lru_cache(maxsize=None)
def parse_all_bases() -> List[BaseItem]:
    """Parse all base item files and return a list of BaseItem objects."""
    all_items = []
    
    # Add debug logging
    logger.debug(f"Searching for base files in: {BASE_DIR}")
    
    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith('.txt'):
                filepath = os.path.join(root, file)
                logger.debug(f"Found file: {filepath}")
                if 'martial weapons' in filepath.lower():
                    logger.debug(f"Found martial weapon file: {filepath}")
                items = parse_item_file(filepath)
                logger.debug(f"Parsed {len(items)} items from {filepath}")
                all_items.extend(items)
                
    logger.debug(f"Total items parsed: {len(all_items)}")
    return all_items

def create_item(filepath: str, name: str, area_level: str) -> BaseItem:
    """Create appropriate item type based on file path."""
    if 'skill-based weapons' in filepath.lower():
        return SkillWeaponItem(name, area_level, filepath)
    elif 'foci' in filepath.lower():
        return DefenseItem(name, area_level, filepath)
    elif 'martial weapons' in filepath.lower():
        return WeaponItem(name, area_level, filepath)
    elif any(x in filepath.lower() for x in ['helmet', 'gloves', 'boots', 'body', 'shields']):
        return DefenseItem(name, area_level, filepath)
    return BaseItem(name, area_level, filepath)

def create_defense_block(item_name, file_path, lines, settings):
    parser = DefenseBaseParser()
    
    # Parse first line for area level info
    min_level, max_level, is_endgame = parser.parse_area_level(lines[0])
    if not min_level:
        return None
        
    # Get defense type from file path
    defense_type = get_defense_type_from_path(file_path)
    
    # For endgame items, determine tier
    if is_endgame:
        defense_values = parser.get_defense_values(lines)
        tier = determine_defense_tier(defense_values, defense_type)
        setting_key = f"SHOW_ENDGAME_T{tier}_{defense_type}"
        style = f"Endgame Tier {tier}"
    else:
        setting_key = f"SHOW_LEVELING_{defense_type}"
        style = "Leveling Armour"
    
    # Generate block based on show/hide setting
    if setting_key in settings.show_settings and settings.show_settings[setting_key]:
        return generate_show_block(item_name, style, min_level, max_level, is_endgame, settings)
    else:
        return generate_hide_block(item_name)

def get_defense_type_from_path(file_path):
    """
    Extract defense type from file path and normalize it
    e.g. bases/body/ArmourEvasion.txt -> ARMOUR_EVASION
    """
    base_name = os.path.basename(file_path)
    defense_type = os.path.splitext(base_name)[0].upper()
    return defense_type

def get_max_defense_values(base_dir, slot_type, defense_type):
    """
    Get maximum defense values for a given slot and defense type
    by scanning all endgame bases
    """
    max_values = {"armour": 0, "evasion": 0, "es": 0}
    parser = DefenseBaseParser()
    
    # Get path for defense type file
    file_path = os.path.join(base_dir, slot_type, f"{defense_type}.txt")
    
    if not os.path.exists(file_path):
        return max_values
        
    # Read and parse file
    with open(file_path, 'r') as f:
        current_block = []
        for line in f:
            line = line.strip()
            if not line:  # Empty line marks end of block
                if current_block:
                    # Only process endgame bases
                    _, _, is_endgame = parser.parse_area_level(current_block[0])
                    if is_endgame:
                        values = parser.get_defense_values(current_block)
                        # Update max values
                        for defense, value in values.items():
                            max_values[defense] = max(max_values[defense], value)
                current_block = []
            else:
                current_block.append(line)
                
        # Process last block if exists
        if current_block:
            _, _, is_endgame = parser.parse_area_level(current_block[0])
            if is_endgame:
                values = parser.get_defense_values(current_block)
                for defense, value in values.items():
                    max_values[defense] = max(max_values[defense], value)
                    
    return max_values

def determine_defense_tier(values, slot, defense_type, base_dir):
    """Determine the tier of a base item based on its text block"""
    
    # Convert defense type to proper case for filename
    file_name = {
        "ARMOUR_EVASION": "ArmourEvasion",
        "ARMOUR_ES": "ArmourES",
        "EVASION_ES": "EvasionES",
        "ARMOUR": "Armour",
        "EVASION": "Evasion",
        "ES": "ES",
        "ARMOUR_SHIELD": "Armour",
        "EVASION_SHIELD": "Evasion",
        "ES_SHIELD": "ES"
    }.get(defense_type.upper(), defense_type)
    
    file_path = os.path.join(base_dir, slot, f"{file_name}.txt")
    
    if not os.path.exists(file_path):
        return 2
        
    with open(file_path, 'r') as f:
        current_block = []
        for line in f:
            line = line.strip()
            if not line:
                if current_block and values:
                    block_values = DefenseBaseParser().get_defense_values(current_block)
                    if block_values == values:
                        for block_line in current_block:
                            if block_line.startswith("Tier"):
                                tier = int(block_line.split()[1])
                                return tier
                current_block = []
                continue
            current_block.append(line)
            
        # Check last block
        if current_block and values:
            block_values = DefenseBaseParser().get_defense_values(current_block)
            if block_values == values:
                for block_line in current_block:
                    if block_line.startswith("Tier"):
                        tier = int(block_line.split()[1])
                        return tier
                
    return 2  # Default to T2 if no tier found

def generate_show_block(item_name, style, min_level, max_level, is_endgame, settings, defense_type, slot):
    """Generate a show block with appropriate style settings"""
    block_lines = []
    
    # Format the defense type and slot for the header
    if defense_type.upper() == "ES":
        defense_name = "ES"
    elif "_" in defense_type:
        # Handle hybrid defenses
        parts = defense_type.split("_")
        defense_name = " ".join(part if part == "ES" else part.title() for part in parts)
    else:
        defense_name = defense_type.title()
    slot_name = slot.upper()
    
    # Add comment header with correct defense type and slot
    if is_endgame:
        block_lines.append(f"# {style.upper()} {defense_name} {slot_name} (Area Level {min_level}+)")
    else:
        block_lines.append(f"# LEVELING {defense_name} {slot_name} (Area Level {min_level}-{max_level})")
    
    # Add show statement and base type
    block_lines.append("Show")
    block_lines.append(f'BaseType "{item_name}"')
    
    # Add area level restriction for leveling items
    if not is_endgame and max_level:
        block_lines.append(f"AreaLevel <= {max_level}")
    
    # Only determine style for non-foci defense items
    if not is_endgame and slot.upper() != "FOCI":
        if "_" in defense_type:
            # Handle hybrid defense styles
            style = f"Leveling {defense_name}"
        elif defense_type.upper() == "ES":
            style = "Leveling ES"
        else:
            style = f"Leveling {defense_name}"
    
    # Add style settings from parsed settings file
    if style in settings.styles:
        logger.debug(f"Applying style '{style}' to {item_name}")
        style_settings = settings.styles[style]
        
        # Handle minimap icon settings separately
        minimap_size = None
        minimap_color = None
        minimap_shape = None
        other_settings = []
        
        for setting, value in style_settings.items():
            if setting == "MinimapIconSize":
                size_map = {"Small": "0", "Medium": "1", "Large": "2"}
                minimap_size = size_map.get(value, "1")
            elif setting == "MinimapIconColour":
                minimap_color = value
            elif setting == "MinimapIconShape":
                minimap_shape = value
            else:
                other_settings.append(f"{setting} {value}")
        
        # Add combined MinimapIcon line immediately after AreaLevel
        if all([minimap_size, minimap_color, minimap_shape]):
            block_lines.append(f"MinimapIcon {minimap_size} {minimap_color} {minimap_shape}")
        
        # Add all other style settings
        block_lines.extend(other_settings)
    else:
        logger.warning(f"Style '{style}' not found in settings. Available styles: {list(settings.styles.keys())}")
        
    return "\n".join(block_lines) + "\n\n"

def generate_hide_block(item_name):
    """Generate a hide block with rarity condition"""
    return f"""Hide
BaseType "{item_name}"
Rarity <= Magic

"""

class FilterGenerator:
    def __init__(self, base_dir, filter_dir, settings):
        self.base_dir = base_dir
        self.filter_dir = filter_dir
        self.settings = settings
        self.defense_parser = DefenseBaseParser()
        self.show_blocks = {
            "endgame_t1": [],
            "endgame_t2": [],
            "leveling": []
        }
        self.hide_blocks = []
        self.endgame_items = {}

    def process_defense_bases(self):
        """Process all defense base types"""
        defense_slots = ["body", "helmet", "gloves", "boots", "shields", "foci"]
        
        for slot in defense_slots:
            slot_dir = os.path.join(self.base_dir, slot)
            if not os.path.exists(slot_dir):
                continue
                
            for filename in os.listdir(slot_dir):
                if not filename.endswith('.txt'):
                    continue
                    
                defense_type = os.path.splitext(filename)[0]
                self.process_defense_file(slot, defense_type)

    def process_defense_file(self, slot, defense_type):
        """Process a single defense base file"""
        file_path = os.path.join(self.base_dir, slot, f"{defense_type}.txt")
        if not os.path.exists(file_path):
            return
        
        current_block = []
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                
                if not line:
                    if current_block:
                        # Convert defense type for settings lookup
                        settings_defense_type = defense_type
                        
                        # Handle hybrid defense types
                        if defense_type.lower() == "armoures":
                            settings_defense_type = "ARMOUR_ES"
                        elif defense_type.lower() == "armourevasion":
                            settings_defense_type = "ARMOUR_EVASION"
                        elif defense_type.lower() == "evasiones":
                            settings_defense_type = "EVASION_ES"
                        
                        self.process_defense_block(current_block, slot, settings_defense_type)
                        current_block = []
                    continue
                
                current_block.append(line)
                
        # Process last block if it exists
        if current_block:
            settings_defense_type = defense_type
            if defense_type.lower() == "armoures":
                settings_defense_type = "ARMOUR_ES"
            elif defense_type.lower() == "armourevasion":
                settings_defense_type = "ARMOUR_EVASION"
            elif defense_type.lower() == "evasiones":
                settings_defense_type = "EVASION_ES"
            
            self.process_defense_block(current_block, slot, settings_defense_type)

    def process_defense_block(self, lines, slot, defense_type):
        """Process a single item block and generate filter block"""
        first_line = lines[0]
        item_name = first_line.split(" (")[0]
        min_level, max_level, is_endgame = self.defense_parser.parse_area_level(first_line)
        
        if not min_level:
            return
        
        values = self.defense_parser.get_defense_values(lines)
        
        # Handle different item types
        if slot.upper() == "SHIELDS":
            if is_endgame:
                tier = determine_defense_tier(values, slot, defense_type, self.base_dir)
                # Convert defense type to match settings format
                shield_type = {
                    "ARMOUR": "ARMOUR",
                    "EVASION": "EVASION",
                    "ARMOUR_EVASION": "ARMOUR_EVASION",
                    "ARMOUR_ES": "ARMOUR_ES"
                }.get(defense_type.upper(), "ARMOUR")  # Default to ARMOUR if not found
                
                settings_key = f"SHOW_ENDGAME_T{tier}_{shield_type}_SHIELD"
                style = f"Endgame {shield_type.replace('_', '/')} Shield T{tier}"
            else:
                settings_key = f"SHOW_LEVELING_{defense_type.upper()}_SHIELD"
                style = f"Leveling {defense_type.title()} Shield"
        elif slot.upper() == "FOCI":
            if is_endgame:
                tier = determine_defense_tier(values, slot, defense_type, self.base_dir)
                settings_key = f"SHOW_ENDGAME_T{tier}_FOCI"
                style = f"Endgame Tier {tier}"
            else:
                settings_key = "SHOW_LEVELING_FOCI"
                style = "Caster Weapon"  # Use Caster Weapon style for leveling foci
        else:
            if is_endgame:
                tier = determine_defense_tier(values, slot, defense_type, self.base_dir)
                settings_key = f"SHOW_ENDGAME_T{tier}_{defense_type.upper()}"
                style = f"Endgame Tier {tier}"
            else:
                settings_key = f"SHOW_LEVELING_{defense_type.upper()}"
                style = f"Leveling {defense_type.title()}"
        
        logger.debug(f"Item: {item_name} | Settings key: {settings_key} | Style: {style}")
        
        # Generate appropriate block based on settings
        if settings_key in self.settings.show_settings and self.settings.show_settings[settings_key]:
            if is_endgame:
                # Store item name for consolidation
                key = (slot, defense_type, tier if 'tier' in locals() else 1)
                if key not in self.endgame_items:
                    self.endgame_items[key] = []
                self.endgame_items[key].append(item_name)
            else:
                block = generate_show_block(item_name, style, min_level, max_level, is_endgame, 
                                      self.settings, defense_type, slot)
                self.show_blocks["leveling"].append((min_level, block))
        else:
            logger.debug(f"Hiding {item_name} because {settings_key} is not True")
            self.hide_blocks.append(generate_hide_block(item_name))

    def get_shield_settings_key(self, defense_type, is_endgame):
        """Get the appropriate settings key for shield items"""
        if is_endgame:
            if defense_type.upper() == "ARMOUR":
                return "SHOW_ENDGAME_T1_ARMOUR_SHIELD"
            elif defense_type.upper() == "EVASION":
                return "SHOW_ENDGAME_T1_EVASION_SHIELD"
            elif defense_type.upper() == "ARMOUR_EVASION":
                return "SHOW_ENDGAME_T1_ARMOUR_EVASION_SHIELD"
            elif defense_type.upper() == "ARMOUR_ES":
                return "SHOW_ENDGAME_T1_ARMOUR_ES_SHIELD"
        else:
            if defense_type.upper() == "ARMOUR":
                return "SHOW_LEVELING_ARMOUR_SHIELD"
            elif defense_type.upper() == "EVASION":
                return "SHOW_LEVELING_EVASION_SHIELD"
            elif defense_type.upper() == "ARMOUR_EVASION":
                return "SHOW_LEVELING_ARMOUR_EVASION_SHIELD"
            elif defense_type.upper() == "ARMOUR_ES":
                return "SHOW_LEVELING_ARMOUR_ES_SHIELD"

    def generate_consolidated_blocks(self):
        """Generate consolidated blocks for endgame items"""
        for (slot, defense_type, tier), items in self.endgame_items.items():
            style = f"Endgame Tier {tier}"
            block = generate_consolidated_show_block(items, style, slot, defense_type, self.settings)
            if tier == 1:
                self.show_blocks["endgame_t1"].append(block)
            else:
                self.show_blocks["endgame_t2"].append(block)

    def generate_filter(self):
        """Generate the complete filter file"""
        try:
            temp_path = os.path.join(SCRIPT_DIR, FILTER_TEMP)
            with open(temp_path, 'w') as f:
                # Write endgame T1 blocks
                f.write("### Endgame Tier 1 Show Blocks ###\n")
                for block in self.show_blocks["endgame_t1"]:
                    f.write(block)
                    
                # Write endgame T2 blocks
                f.write("\n### Endgame Tier 2 Show Blocks ###\n")
                for block in self.show_blocks["endgame_t2"]:
                    f.write(block)
                    
                # Write leveling blocks in descending order
                f.write("\n### Leveling Show Blocks ###\n")
                sorted_leveling = sorted(self.show_blocks["leveling"], 
                                      key=lambda x: x[0], 
                                      reverse=True)
                for _, block in sorted_leveling:
                    f.write(block)
                    
                # Write rare safeguard
                f.write("\n### Rare Item Safeguard ###\n")
                f.write("Show\nRarity >= Rare\n\n")
                
                # Include base filter
                base_filter_path = os.path.join(SCRIPT_DIR, FILTER_BASE)
                if os.path.exists(base_filter_path):
                    with open(base_filter_path, 'r') as bf:
                        f.write(bf.read())
                        
                # Write hide blocks
                write_hide_blocks = True
                settings_path = os.path.join(SCRIPT_DIR, 'filtersettings.txt')
                with open(settings_path, 'r') as settings_file:
                    for line in settings_file:
                        if line.strip().startswith('HIDE_UNSHOWN_ITEMS'):
                            write_hide_blocks = 'True' in line
                            break
                
                if write_hide_blocks:
                    f.write("\n### Hide Blocks ###\n")
                    for block in self.hide_blocks:
                        f.write(block)
                    
            # Rename temp file to final output
            output_path = os.path.join(SCRIPT_DIR, FILTER_OUTPUT)
            os.replace(temp_path, output_path)
        except Exception as e:
            logger.error(f"Error generating filter: {e}")
            raise

def generate_consolidated_show_block(items, style, slot, defense_type, settings):
    """Generate a show block for multiple items with the same tier and slot"""
    block_lines = []
    
    # Add header
    block_lines.append(f"# {style.upper()} {defense_type.title()} {slot.upper()} (Area Level 63+)")
    
    # Add show statement and combined base types
    block_lines.append("Show")
    base_types = '" "'.join(items)
    block_lines.append(f'BaseType "{base_types}"')
    
    # Add style settings with correct MinimapIcon format
    if style in settings.styles:
        style_settings = settings.styles[style]
        
        # Convert MinimapIcon settings
        icon_size = style_settings.get("MinimapIconSize", "")
        icon_color = style_settings.get("MinimapIconColour", "")
        icon_shape = style_settings.get("MinimapIconShape", "")
        
        if icon_size and icon_color and icon_shape:
            size_value = {"Large": "0", "Medium": "1", "Small": "2"}.get(icon_size, "0")
            block_lines.append(f"MinimapIcon {size_value} {icon_color} {icon_shape}")
        
        # Add other style settings
        for setting, value in style_settings.items():
            if not setting.startswith("MinimapIcon"):  # Skip individual minimap settings
                block_lines.append(f"{setting} {value}")
                
    return "\n".join(block_lines) + "\n\n"

class WeaponFilterGenerator(FilterBlockGenerator):
    def __init__(self, settings: FilterSettings):
        super().__init__(settings)
        
    def _get_weapon_type(self, item: BaseItem) -> str:
        """Get the weapon type from filepath."""
        if not item._filepath:
            return "UNKNOWN"
        
        # Normalize path separators
        filepath = item._filepath.replace('\\', '/')
        
        # Extract filename without extension
        filename = os.path.splitext(os.path.basename(filepath))[0].upper()
        
        # Handle special cases
        if "ONEHANDMACES" in filename:
            return "ONE_HAND_MACES"
        elif "TWOHANDMACES" in filename:
            return "TWO_HAND_MACES"
        elif "QUARTERSTAVES" in filename:
            return "QUARTERSTAVES"
        
        return filename

    def _create_header(self, item: BaseItem) -> str:
        """Create the descriptive header comment."""
        parts = []
        
        # Handle skill weapons differently
        if isinstance(item, SkillWeaponItem) and item.granted_skill:
            weapon_type = (
                'WANDS' if 'wands' in item._filepath.lower() else
                'STAVES' if 'staves' in item._filepath.lower() else
                'SCEPTRES' if 'sceptres' in item._filepath.lower() else
                'UNKNOWN'
            )
            return f"# {item.granted_skill.upper()} {weapon_type}"
            
        # Handle quivers
        if isinstance(item, QuiverItem):
            return f"# {item.name}"
            
        # Handle martial weapons
        if item.is_endgame:
            parts.append("ENDGAME")
            if "Expert" in item.name:
                parts.append("T1")
            elif "Advanced" in item.name:
                parts.append("T2")
        else:
            parts.append("LEVELING")
            
        parts.append(self._get_weapon_type(item))
        parts.append(f"({item.area_level})")
        
        return f"# {' '.join(parts)}"

    def create_block(self, item: BaseItem, show: bool = True, style: Optional[str] = None) -> str:
        """Create a filter block for a weapon."""
        lines = []
        
        # Add header comment
        if isinstance(item, WeaponItem) and not isinstance(item, (SkillWeaponItem, QuiverItem)):
            if "+" in item.area_level:  # Endgame item
                tier_str = f"T{item.tier}" if hasattr(item, 'tier') else ""
                lines.append(f"# ENDGAME {tier_str} {self._get_weapon_type(item)} ({item.area_level})")
            else:  # Leveling item
                lines.append(f"# LEVELING {self._get_weapon_type(item)} ({item.area_level})")
        else:
            lines.append(self._create_header(item))
        
        # Add show/hide line
        lines.append("Show" if show else "Hide")
        
        # Add base type
        lines.append(f'BaseType "{item.name}"')
        
        # Add area level condition for leveling items that are being shown
        if show and not "+" in item.area_level and item.area_level:
            try:
                level_match = re.search(r'(?:Area Level )?(\d+)-(\d+)', item.area_level)
                if level_match:
                    max_level = int(level_match.group(2))
                    lines.append(f"AreaLevel <= {max_level}")
            except Exception as e:
                print(f"Warning: Could not parse area level from {item.area_level}: {e}")
        
        # Add style if showing
        if show and style in self.settings.styles:
            style_dict = self.settings.styles[style]
            
            # Process minimap icon settings separately
            minimap_size = None
            minimap_colour = None
            minimap_shape = None
            
            style_lines = []
            for key, value in style_dict.items():
                if key == "MinimapIconSize":
                    # Correct mapping: Large = 0, Medium = 1, Small = 2
                    size_map = {"Large": "0", "Medium": "1", "Small": "2"}
                    minimap_size = size_map.get(value, "1")
                elif key == "MinimapIconColour":
                    minimap_colour = value
                elif key == "MinimapIconShape":
                    minimap_shape = value
                else:
                    style_lines.append(f"{key} {value}")
            
            # Add minimap icon line if all components are present
            if all([minimap_size, minimap_colour, minimap_shape]):
                style_lines.insert(0, f"MinimapIcon {minimap_size} {minimap_colour} {minimap_shape}")
            
            lines.extend(style_lines)
            
        # Add rarity condition for hide blocks
        if not show:
            lines.append("Rarity <= Magic")
            
        # Add TWO blank lines at end for spacing between blocks
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)

    def _format_style(self, style: Dict[str, str]) -> List[str]:
        """Format style dictionary into filter syntax lines."""
        # Process minimap icon settings separately
        minimap_size = None
        minimap_colour = None
        minimap_shape = None
        
        lines = []
        for key, value in style.items():
            if key == "MinimapIconSize":
                size_map = {"Large": "0", "Medium": "1", "Small": "2"}
                minimap_size = size_map.get(value, "1")
            elif key == "MinimapIconColour":
                minimap_colour = value
            elif key == "MinimapIconShape":
                minimap_shape = value
            else:
                lines.append(f"{key} {value}")
        
        # Add minimap icon line if all components are present
        if all([minimap_size, minimap_colour, minimap_shape]):
            lines.insert(0, f"MinimapIcon {minimap_size} {minimap_colour} {minimap_shape}")
            
        return lines

def parse_skill_weapon_file(filepath: str) -> List[SkillWeaponItem]:
    """Parse a skill weapon file and return a list of SkillWeaponItem objects."""
    items = []
    current_name = None
    current_skill = None
    
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            
            # Check if this is a weapon name line (doesn't start with space or keywords)
            if not line.startswith(' ') and not line.startswith('Requires:') and not line.startswith('Spirit:') and not line.startswith('Grants Skill:'):
                # If we have a complete weapon from previous iteration, add it
                if current_name and current_skill:
                    item = SkillWeaponItem(current_name, "1", filepath)
                    item.skill_name = current_skill
                    items.append(item)
                
                # Start new weapon
                current_name = line
                current_skill = None
                
            # Check if this is a skill grant line
            elif 'Grants Skill:' in line:
                current_skill = line.split('Grants Skill:')[1].strip()
                
    # Add the last item
    if current_name and current_skill:
        item = SkillWeaponItem(current_name, "1", filepath)
        item.skill_name = current_skill
        items.append(item)
        
    return items

def process_skill_weapon_blocks(items: List[SkillWeaponItem], settings: FilterSettings) -> Tuple[List[str], List[str]]:
    """Process skill weapons and generate show/hide blocks based on their granted skills."""
    generator = WeaponFilterGenerator(settings)
    show_blocks = []
    hide_blocks = []
    
    # Group items by weapon type and skill
    skill_groups = {}
    
    for item in items:
        if 'wands' in item._filepath.lower():
            weapon_type = 'WANDS'
        elif 'staves' in item._filepath.lower():
            weapon_type = 'STAVES'
        elif 'sceptres' in item._filepath.lower():
            weapon_type = 'SCEPTRES'
        else:
            continue
            
        # Special case for Purity Sceptres
        if item.name == "Shrine Sceptre" and "Purity" in item.skill_name:
            key = ("SCEPTRES", "Purity")
            setting_key = "SHOW_PURITY_SCEPTRES"
        else:
            key = (weapon_type, item.skill_name)
            setting_key = f"SHOW_{item.skill_name.upper().replace(' ', '_')}_{weapon_type}"
            
        if key not in skill_groups:
            skill_groups[key] = {"items": [], "setting": setting_key}
        skill_groups[key]["items"].append(item)
    
    # Create consolidated blocks for each group
    for (weapon_type, skill_name), group in skill_groups.items():
        if settings.show_settings.get(group["setting"], False):
            items = group["items"]
            base_types = [f'"{item.name}"' for item in items]
            
            # Special header for Purity Sceptres
            if skill_name == "Purity":
                header = "# SCEPTRES - Purity"
            else:
                header = f"# {weapon_type} - {skill_name}"
                
            block = f"{header}\n"
            block += "Show\n"
            block += f'BaseType {" ".join(base_types)}\n'
            
            # Apply the Caster Weapon style from settings
            if "Caster Weapon" in settings.styles:
                style_dict = settings.styles["Caster Weapon"]
                
                # Process minimap icon settings first
                minimap_size = None
                minimap_colour = None
                minimap_shape = None
                style_lines = []
                
                for key, value in style_dict.items():
                    if key == "MinimapIconSize":
                        size_map = {"Large": "0", "Medium": "1", "Small": "2"}
                        minimap_size = size_map.get(value, "1")
                    elif key == "MinimapIconColour":
                        minimap_colour = value
                    elif key == "MinimapIconShape":
                        minimap_shape = value
                    else:
                        style_lines.append(f"{key} {value}")
                
                # Add minimap icon line first if all components are present
                if all([minimap_size, minimap_colour, minimap_shape]):
                    block += f"MinimapIcon {minimap_size} {minimap_colour} {minimap_shape}\n"
                
                # Add remaining style lines
                block += "\n".join(style_lines)
                block += "\n"
            
            block += "\n"
            show_blocks.append(block)
        else:
            for item in group["items"]:
                block = f"# {weapon_type} - {skill_name}\n"
                block += "Hide\n"
                block += f'BaseType "{item.name}"\n'
                block += "Rarity <= Magic\n\n"
                hide_blocks.append(block)
    
    return show_blocks, hide_blocks

def parse_quiver_file(filepath: str) -> List[QuiverItem]:
    """Parse a quiver file and return a list of QuiverItem objects."""
    items = []
    current_name = None
    current_effect = None

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue            
            # Check if this is a quiver name line (must end in "Quiver")
            if line.endswith("Quiver"):
                # If we have a complete quiver from previous iteration, add it
                if current_name and current_effect:
                    item = QuiverItem(current_name, "1", filepath)
                    item.implicit_effect = current_effect
                    items.append(item)
                
                # Start new quiver
                current_name = line
                current_effect = None
            else:
                # This must be an effect line
                current_effect = line
                
    # Add the last item
    if current_name and current_effect:
        item = QuiverItem(current_name, "1", filepath)
        item.implicit_effect = current_effect
        items.append(item)
        
    return items

def process_quiver_blocks(items: List[QuiverItem], settings: FilterSettings) -> Tuple[List[str], List[str]]:
    """Process quiver items and return show/hide blocks."""
    generator = WeaponFilterGenerator(settings)
    show_blocks = []
    hide_blocks = []
    
    for item in items:
        # Create setting key based on effect
        if "Physical Damage" in item.implicit_effect:
            setting_key = "SHOW_PHYSICAL_DAMAGE_QUIVER"
        elif "Fire damage" in item.implicit_effect or "Fire Damage" in item.implicit_effect:  # Handle both capitalizations
            setting_key = "SHOW_FIRE_DAMAGE_QUIVER"
        elif "Life" in item.implicit_effect:
            setting_key = "SHOW_LIFE_ON_HIT_QUIVER"
        elif "Accuracy" in item.implicit_effect:
            setting_key = "SHOW_ACCURACY_QUIVER"
        elif "Stun Threshold" in item.implicit_effect:
            setting_key = "SHOW_STUN_THRESHOLD_QUIVER"
        elif "Poison" in item.implicit_effect:
            setting_key = "SHOW_POISON_CHANCE_QUIVER"
        elif "Bleeding" in item.implicit_effect or "cause Bleeding" in item.implicit_effect:
            setting_key = "SHOW_BLEED_CHANCE_QUIVER"
        elif "Attack Speed" in item.implicit_effect:
            setting_key = "SHOW_ATTACK_SPEED_QUIVER"
        elif "Pierce" in item.implicit_effect:
            setting_key = "SHOW_PIERCE_QUIVER"
        elif "Arrow Speed" in item.implicit_effect:
            setting_key = "SHOW_ARROW_SPEED_QUIVER"
        elif "Critical" in item.implicit_effect or "Critical Hit Chance" in item.implicit_effect:
            setting_key = "SHOW_CRIT_CHANCE_QUIVER"
        else:
            continue
        show = settings.show_settings.get(setting_key, False)
        
        if show:
            block = generator.create_block(item, True, "Leveling Martial Weapon")
            show_blocks.append(block)
        else:
            block = generator.create_block(item, False)
            hide_blocks.append(block)
            
    return show_blocks, hide_blocks

def process_weapon_blocks(items: List[BaseItem], settings: FilterSettings) -> Tuple[Dict[str, List[str]], List[str]]:
    """Process weapon items and return show/hide blocks."""
    generator = WeaponFilterGenerator(settings)
    show_blocks = {
        "endgame_t1": [],
        "endgame_t2": [],
        "leveling": [],
        "skill": [],
        "quiver": []
    }
    hide_blocks = []

    # Group endgame weapons by type and tier
    endgame_groups = {}  # key: (tier, weapon_type), value: list of items
    leveling_groups = {}  # key: (weapon_type, max_level), value: list of items
    
    print(f"\nProcessing {len(items)} total items")
    
    for item in items:
        if isinstance(item, WeaponItem) and not isinstance(item, (SkillWeaponItem, QuiverItem)):
            weapon_type = generator._get_weapon_type(item)
            is_endgame = "+" in item.area_level
            
            if is_endgame:
                tier = getattr(item, 'tier', None)
                if tier:
                    setting_key = f"SHOW_ENDGAME_T{tier}_{weapon_type}"
                    show = settings.show_settings.get(setting_key, False)
                    
                    if show:
                        key = (tier, weapon_type)
                        if key not in endgame_groups:
                            endgame_groups[key] = []
                        endgame_groups[key].append(item)
                    else:
                        hide_blocks.append(generator.create_block(item, False))
            else:
                setting_key = f"SHOW_LEVELING_{weapon_type}"
                show = settings.show_settings.get(setting_key, False)
                
                if show:
                    level_match = re.search(r'(?:Area Level )?(\d+)-(\d+)', item.area_level)
                    if level_match:
                        max_level = int(level_match.group(2))
                        key = (weapon_type, max_level)
                        if key not in leveling_groups:
                            leveling_groups[key] = []
                        leveling_groups[key].append(item)
                else:
                    hide_blocks.append(generator.create_block(item, False))

    # Create consolidated blocks for endgame weapons
    for (tier, weapon_type), items in endgame_groups.items():
        if items:
            style = f"Endgame Tier {tier}"
            block = generator.create_consolidated_block(items, True, style)
            show_blocks[f"endgame_t{tier}"].append(block)

    # Create consolidated blocks for leveling weapons
    for (weapon_type, max_level), items in leveling_groups.items():
        if items:
            block = generator.create_consolidated_block(items, True, "Leveling Martial Weapon")
            show_blocks["leveling"].append((max_level, block))

    return show_blocks, hide_blocks

def main():
    settings = FilterSettings(os.path.join(os.path.dirname(__file__), 'filtersettings.txt'))
    
    # Process defense items
    defense_generator = FilterGenerator(BASE_DIR, FILTER_DIR, settings)
    defense_generator.process_defense_bases()
    defense_generator.generate_consolidated_blocks()
    
    # Process martial weapons (keep existing logic)
    weapon_items = []
    for root, _, files in os.walk(os.path.join(BASE_DIR, 'martial weapons')):
        for file in files:
            if file.endswith('.txt'):
                filepath = os.path.join(root, file)
                items = parse_item_file(filepath)
                weapon_items.extend(items)
    
    weapon_show_blocks, weapon_hide_blocks = process_weapon_blocks(weapon_items, settings)
    
    # Process skill weapons
    skill_items = []
    skill_weapon_dir = os.path.join(BASE_DIR, 'skill-based weapons')
    if os.path.exists(skill_weapon_dir):
        for file in os.listdir(skill_weapon_dir):
            if file.endswith('.txt'):
                filepath = os.path.join(skill_weapon_dir, file)
                skill_items.extend(parse_skill_weapon_file(filepath))
    
    skill_show_blocks, skill_hide_blocks = process_skill_weapon_blocks(skill_items, settings)
    
    # Process quivers separately
    quiver_items = []
    quiver_dir = os.path.join(BASE_DIR, 'quivers')
    if os.path.exists(quiver_dir):
        for file in os.listdir(quiver_dir):
            if file.endswith('.txt'):
                filepath = os.path.join(quiver_dir, file)
                quiver_items.extend(parse_quiver_file(filepath))
    
    quiver_show_blocks, quiver_hide_blocks = process_quiver_blocks(quiver_items, settings)
    
    # Add skill blocks to weapon blocks
    weapon_show_blocks['skill'] = skill_show_blocks
    weapon_hide_blocks.extend(skill_hide_blocks)
    
    # Add quiver blocks to weapon blocks
    weapon_show_blocks['quiver'] = quiver_show_blocks
    weapon_hide_blocks.extend(quiver_hide_blocks)
    
    # Generate combined filter
    try:
        temp_path = os.path.join(SCRIPT_DIR, FILTER_TEMP)
        with open(temp_path, 'w') as f:
            # Write endgame T1 blocks
            f.write("### Endgame Tier 1 Show Blocks ###\n")
            for block in defense_generator.show_blocks["endgame_t1"]:
                if isinstance(block, tuple):
                    _, block_text = block
                    f.write(block_text)
                else:
                    f.write(block)
            for block in weapon_show_blocks["endgame_t1"]:
                f.write(block)
                
            # Write endgame T2 blocks
            f.write("\n### Endgame Tier 2 Show Blocks ###\n")
            for block in defense_generator.show_blocks["endgame_t2"]:
                if isinstance(block, tuple):
                    _, block_text = block
                    f.write(block_text)
                else:
                    f.write(block)
            for block in weapon_show_blocks["endgame_t2"]:
                f.write(block)
                
            # Write skill weapon blocks
            f.write("\n### Skill Weapon Show Blocks ###\n")
            for block in weapon_show_blocks["skill"]:
                f.write(block)
                
            # Write quiver blocks
            f.write("\n### Quiver Show Blocks ###\n")
            for block in weapon_show_blocks["quiver"]:
                f.write(block)
                
            # Write leveling blocks
            f.write("\n### Leveling Show Blocks ###\n")
            # Sort defense leveling blocks by level
            defense_leveling = []
            for block in defense_generator.show_blocks["leveling"]:
                if isinstance(block, tuple):
                    level, block_text = block
                    defense_leveling.append((level, block_text))
                else:
                    defense_leveling.append((0, block))
            
            # Combine and sort all leveling blocks
            all_leveling = defense_leveling + [(level, block) for level, block in weapon_show_blocks["leveling"]]
            for _, block in sorted(all_leveling, key=lambda x: x[0], reverse=True):
                f.write(block)
                
            # Write rare safeguard
            f.write("\n### Rare Item Safeguard ###\n")
            f.write("Show\nRarity >= Rare\n\n")
            
            # Include base filter
            base_filter_path = os.path.join(SCRIPT_DIR, FILTER_BASE)
            if os.path.exists(base_filter_path):
                with open(base_filter_path, 'r') as bf:
                    f.write(bf.read())
                    
            # Write hide blocks
            write_hide_blocks = True
            settings_path = os.path.join(SCRIPT_DIR, 'filtersettings.txt')
            with open(settings_path, 'r') as settings_file:
                for line in settings_file:
                    if line.strip().startswith('HIDE_UNSHOWN_ITEMS'):
                        write_hide_blocks = 'True' in line
                        break
            
            if write_hide_blocks:
                f.write("\n### Hide Blocks ###\n")
                for block in defense_generator.hide_blocks:
                    f.write(block)
                for block in weapon_hide_blocks:
                    f.write(block)
                
        # Rename temp file to final output
        output_path = os.path.join(SCRIPT_DIR, FILTER_OUTPUT)
        os.replace(temp_path, output_path)
        
    except Exception as e:
        logger.error(f"Error generating filter: {e}")
        raise

if __name__ == "__main__":
    main()