import os
import sys

# Ensure CWD is always the project root so paths and logs are correct even if spawned from IDEs or Applescript
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)

import platform
import subprocess
import time
import logging
from dotenv import load_dotenv, set_key

# --- LOGGING SETUP ---
# Capture full pipeline trace (INFO+) to file, keeping the terminal clean
logging.basicConfig(
    filename=os.path.join(PROJECT_ROOT, 'cli_errors.log'),
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    force=True
)
# Silence noisy third-party library debug logs — keep only our code
for noisy in ('urllib3', 'requests', 'charset_normalizer', 'faiss'):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# --- RETRY SETTINGS ---
MAX_RETRIES = 5
BASE_DELAY = 2

def _is_rate_limited_(error_msg):
    err_str = str(error_msg).lower()
    return "429" in err_str or "rate" in err_str or "rate-limited" in err_str or "too many requests" in err_str

# --- 0. TERMINAL POPUP LOGIC ---
def summon_terminal():
    if "--spawned" in sys.argv:
        # We are already in the spawned terminal
        sys.argv.remove("--spawned")
        return
    
    # Check if we should spawn based on user prompt requirements.
    # We will spawn a new terminal instead of running inside the IDE's terminal.
    system = platform.system()
    try:
        if system == "Windows":
            # Spawn a new cmd window and run this script
            subprocess.Popen(['start', 'cmd', '/k', sys.executable] + sys.argv + ['--spawned'], shell=True)
            sys.exit(0)
        elif system == "Darwin":
            # Spawn a new Terminal window on macOS
            script_path = os.path.abspath(sys.argv[0])
            args = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            script = f'''
            tell application "Terminal"
                activate
                do script "{sys.executable} \\"{script_path}\\" {args} --spawned"
            end tell
            '''
            subprocess.Popen(['osascript', '-e', script])
            sys.exit(0)
        # Linux isn't explicitly required, will proceed in current terminal
    except Exception as e:
        print(f"Could not spawn terminal: {e}")
        # Proceed in current terminal if spawning fails

summon_terminal()

# --- IMPORTS ---
# Delayed imports to keep the popup fast and avoid loading heavy ML models prematurely
from src.adaptive_routing import (
    FrameworkConfig, 
    TriageModule, 
    SemanticRouterModule, 
    LegalRetrievalModule
)

# ═══════════════════════════════════════════════════════════════
# ANSI COLOR CONSTANTS
# ═══════════════════════════════════════════════════════════════
CYAN    = '\033[96m'
BLUE    = '\033[94m'
YELLOW  = '\033[93m'
GREEN   = '\033[92m'
RED     = '\033[91m'
MAGENTA = '\033[95m'
WHITE   = '\033[97m'
DIM     = '\033[2m'
BOLD    = '\033[1m'
RESET   = '\033[0m'

# ═══════════════════════════════════════════════════════════════
# 1. UI HELPERS
# ═══════════════════════════════════════════════════════════════
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = f"""{BLUE}
    ╔══════════════════════════════════════════════════════╗{CYAN}
    ║  _       __  __  ____  _____                         ║
    ║ | |     / _ \\|  _ \\|  ___|                         ║
    ║ | |    | |_| | |_) | |_                              ║
    ║ | |___ |  _  |  _ <|  _|                             ║
    ║ |_____||_| |_|_| \\_\\_|                             ║
    ║                                                      ║{YELLOW}
    ║   Legal Adaptive Routing Framework                   ║
    ║   Philippine & Hong Kong Legal Queries               ║{BLUE}
    ╠══════════════════════════════════════════════════════╣{RESET}
    ║  Team 404FoundUs  │  Saint Louis University          ║{BLUE}
    ╚══════════════════════════════════════════════════════╝{RESET}
    """
    print(banner)

def print_divider(char="─", width=60):
    print(f"{DIM}{char * width}{RESET}")

def print_section_header(title, color=CYAN):
    print(f"\n{color}{BOLD}{'─' * 4} {title} {'─' * (53 - len(title))}{RESET}")

def print_error_box(stage, message, hint=None):
    """Print a formatted error box with optional config hint."""
    print(f"\n{RED}┌{'─' * 58}┐{RESET}")
    print(f"{RED}│{BOLD} ✗ ERROR: {stage:<48}{RESET}{RED}│{RESET}")
    print(f"{RED}├{'─' * 58}┤{RESET}")
    # Word-wrap the message to fit the box
    for line in _wrap_text_(str(message), 56):
        print(f"{RED}│{RESET} {line:<56} {RED}│{RESET}")
    if hint:
        print(f"{RED}├{'─' * 58}┤{RESET}")
        print(f"{RED}│{YELLOW}{BOLD} 💡 Hint:{RESET}{' ' * 49}{RED}│{RESET}")
        for line in _wrap_text_(hint, 56):
            print(f"{RED}│{RESET} {YELLOW}{line:<56}{RESET} {RED}│{RESET}")
    print(f"{RED}└{'─' * 58}┘{RESET}")

def print_status_box(label, value, color=GREEN):
    """Print a small inline status indicator."""
    icon = "✓" if color == GREEN else "⚠" if color == YELLOW else "✗"
    print(f"  {color}{icon}{RESET} {label}: {color}{value}{RESET}")

def _wrap_text_(text, width):
    """Simple word-wrap for box display."""
    lines = []
    for raw_line in text.split('\n'):
        while len(raw_line) > width:
            # Find last space within width
            break_at = raw_line.rfind(' ', 0, width)
            if break_at == -1:
                break_at = width
            lines.append(raw_line[:break_at])
            raw_line = raw_line[break_at:].lstrip()
        lines.append(raw_line)
    return lines

def _bool_str_(val):
    """Display bool as colored ON/OFF."""
    if val:
        return f"{GREEN}ON{RESET}"
    return f"{RED}OFF{RESET}"

def _input_bool_(prompt, current):
    """Prompt user for a boolean toggle (on/off)."""
    display = "ON" if current else "OFF"
    val = input(f"  {prompt} (currently {display}) [on/off/skip]: ").strip().lower()
    if val in ('on', 'true', 'yes', '1'):
        return True
    elif val in ('off', 'false', 'no', '0'):
        return False
    return current

def _input_float_(prompt, current):
    """Prompt user for a float value."""
    val = input(f"  {prompt} (currently {current}): ").strip()
    if not val:
        return current
    try:
        return float(val)
    except ValueError:
        print(f"  {RED}Invalid number. Keeping {current}.{RESET}")
        return current

def _input_int_(prompt, current):
    """Prompt user for an int value."""
    val = input(f"  {prompt} (currently {current}): ").strip()
    if not val:
        return current
    try:
        return int(val)
    except ValueError:
        print(f"  {RED}Invalid number. Keeping {current}.{RESET}")
        return current

# ═══════════════════════════════════════════════════════════════
# 2. CONFIGURATION MENU (Complete)
# ═══════════════════════════════════════════════════════════════

# Configuration state stored as a dict for clean access
_config = {}

def _load_config_from_env_():
    """Load all configuration values from .env with defaults from FrameworkConfig."""
    load_dotenv()
    return {
        # API
        "api_key":              os.getenv("OPENROUTER_API_KEY", ""),
        # Triage Module
        "triage_model":         os.getenv("TRIAGE_MODEL", "z-ai/glm-4.5-air:free"),
        "triage_temp":          float(os.getenv("TRIAGE_TEMP", "0.6")),
        "triage_max_tokens":    int(os.getenv("TRIAGE_MAX_TOKENS", "1500")),
        "triage_use_system":    os.getenv("TRIAGE_USE_SYSTEM", "True").lower() == "true",
        "triage_reasoning":     os.getenv("TRIAGE_REASONING", "True").lower() == "true",
        # Router Module
        "router_model":         os.getenv("ROUTER_MODEL", "z-ai/glm-4.5-air:free"),
        "router_temp":          float(os.getenv("ROUTER_TEMP", "0.0")),
        "router_max_tokens":    int(os.getenv("ROUTER_MAX_TOKENS", "200")),
        "router_use_system":    os.getenv("ROUTER_USE_SYSTEM", "False").lower() == "true",
        "router_reasoning":     os.getenv("ROUTER_REASONING", "False").lower() == "true",
        # General LLM
        "general_model":        os.getenv("GENERAL_MODEL", "z-ai/glm-4.5-air:free"),
        "general_temp":         float(os.getenv("GENERAL_TEMP", "0.5")),
        "general_max_tokens":   int(os.getenv("GENERAL_MAX_TOKENS", "2000")),
        "general_use_system":   os.getenv("GENERAL_USE_SYSTEM", "False").lower() == "true",
        "general_reasoning":    os.getenv("GENERAL_REASONING", "False").lower() == "true",
        # Reasoning LLM
        "reasoning_model":      os.getenv("REASONING_MODEL", "z-ai/glm-4.5-air:free"),
        "reasoning_temp":       float(os.getenv("REASONING_TEMP", "0.7")),
        "reasoning_max_tokens": int(os.getenv("REASONING_MAX_TOKENS", "3000")),
        "reasoning_use_system": os.getenv("REASONING_USE_SYSTEM", "False").lower() == "true",
        "reasoning_reasoning":  os.getenv("REASONING_REASONING", "True").lower() == "true",
        # Casual LLM
        "casual_model":         os.getenv("CASUAL_MODEL", "z-ai/glm-4.5-air:free"),
        "casual_temp":          float(os.getenv("CASUAL_TEMP", "0.8")),
        "casual_max_tokens":    int(os.getenv("CASUAL_MAX_TOKENS", "200")),
        "casual_use_system":    os.getenv("CASUAL_USE_SYSTEM", "True").lower() == "true",
        "casual_reasoning":     os.getenv("CASUAL_REASONING", "False").lower() == "true",
        # Network
        "request_timeout":      int(os.getenv("REQUEST_TIMEOUT", "30")),
        "retry_count":          int(os.getenv("RETRY_COUNT", "2")),
        "retry_backoff":        float(os.getenv("RETRY_BACKOFF", "1.0")),
    }

def _print_module_config_(name, cfg, prefix):
    """Print a single module's configuration in a formatted table."""
    print(f"  {'Model:':<18} {CYAN}{cfg[f'{prefix}_model']}{RESET}")
    print(f"  {'Temperature:':<18} {cfg[f'{prefix}_temp']}")
    print(f"  {'Max Tokens:':<18} {cfg[f'{prefix}_max_tokens']}")
    print(f"  {'System Role:':<18} {_bool_str_(cfg[f'{prefix}_use_system'])}")
    print(f"  {'Reasoning:':<18} {_bool_str_(cfg[f'{prefix}_reasoning'])}")

def _edit_module_config_(name, cfg, prefix):
    """Interactive editor for a single module's config."""
    print(f"\n{CYAN}{BOLD}  Editing: {name}{RESET}")
    print_divider("─", 50)
    cfg[f"{prefix}_model"] = input(f"  Model (currently {cfg[f'{prefix}_model']}): ").strip() or cfg[f"{prefix}_model"]
    cfg[f"{prefix}_temp"] = _input_float_("Temperature", cfg[f"{prefix}_temp"])
    cfg[f"{prefix}_max_tokens"] = _input_int_("Max Tokens", cfg[f"{prefix}_max_tokens"])
    cfg[f"{prefix}_use_system"] = _input_bool_("System Role", cfg[f"{prefix}_use_system"])
    cfg[f"{prefix}_reasoning"] = _input_bool_("Reasoning", cfg[f"{prefix}_reasoning"])
    print(f"  {GREEN}✓ {name} configuration updated.{RESET}")

def interactive_config():
    """Full interactive configuration menu with sub-menus for each module."""
    global _config
    _config = _load_config_from_env_()
    
    modules = [
        ("Triage Module",    "triage"),
        ("Router Module",    "router"),
        ("General LLM",      "general"),
        ("Reasoning LLM",    "reasoning"),
        ("Casual LLM",       "casual"),
    ]

    while True:
        clear_screen()
        print_banner()
        print_section_header("FRAMEWORK CONFIGURATION")
        
        # API Key
        key_status = f"{GREEN}[SET]{RESET}" if _config["api_key"] else f"{RED}[NOT SET]{RESET}"
        print(f"\n  {BOLD}0.{RESET} API Key: {key_status}")
        print()
        
        # Module summary table
        for i, (name, prefix) in enumerate(modules, 1):
            sys_status = _bool_str_(_config[f"{prefix}_use_system"])
            reas_status = _bool_str_(_config[f"{prefix}_reasoning"])
            model = _config[f"{prefix}_model"]
            print(f"  {BOLD}{i}.{RESET} {name:<18} │ {CYAN}{model:<30}{RESET} │ Sys: {sys_status}  Reas: {reas_status}")
        
        print()
        print(f"  {BOLD}6.{RESET} Network Settings   │ Timeout: {_config['request_timeout']}s  Retries: {_config['retry_count']}  Backoff: {_config['retry_backoff']}s")
        
        print_divider()
        print(f"  {BOLD}S.{RESET} Save and Start Chat")
        print(f"  {BOLD}Q.{RESET} Quit")
        
        choice = input(f"\n  Select option (0-6, S, Q): ").strip().upper()
        
        if choice == '0':
            _config["api_key"] = input("  Enter OpenRouter API Key: ").strip() or _config["api_key"]
        elif choice in ('1', '2', '3', '4', '5'):
            idx = int(choice) - 1
            name, prefix = modules[idx]
            _edit_module_config_(name, _config, prefix)
            input(f"\n  Press Enter to continue...")
        elif choice == '6':
            print(f"\n{CYAN}{BOLD}  Editing: Network Settings{RESET}")
            print_divider("─", 50)
            _config["request_timeout"] = _input_int_("Request Timeout (seconds)", _config["request_timeout"])
            _config["retry_count"] = _input_int_("Retry Count", _config["retry_count"])
            _config["retry_backoff"] = _input_float_("Retry Backoff (seconds)", _config["retry_backoff"])
            print(f"  {GREEN}✓ Network settings updated.{RESET}")
            input(f"\n  Press Enter to continue...")
        elif choice == 'S':
            break
        elif choice == 'Q':
            print(f"\n  {YELLOW}Exiting...{RESET}")
            sys.exit(0)

    # Apply ALL configuration to FrameworkConfig
    _apply_config_(_config)
    
    # Ask to save
    save_ans = input(f"\n  Save configuration to .env? (y/n): ").strip().lower()
    if save_ans == 'y':
        _save_config_to_env_(_config)

def _apply_config_(cfg):
    """Apply the full configuration dict to FrameworkConfig."""
    FrameworkConfig._update_settings_(
        api_key=cfg["api_key"],
        # Triage
        triage_model=cfg["triage_model"],
        triage_temp=cfg["triage_temp"],
        triage_max_tokens=cfg["triage_max_tokens"],
        triage_use_system=cfg["triage_use_system"],
        triage_reasoning=cfg["triage_reasoning"],
        # Router
        router_model=cfg["router_model"],
        router_temp=cfg["router_temp"],
        router_max_tokens=cfg["router_max_tokens"],
        router_use_system=cfg["router_use_system"],
        router_reasoning=cfg["router_reasoning"],
        # General
        general_model=cfg["general_model"],
        general_temp=cfg["general_temp"],
        general_max_tokens=cfg["general_max_tokens"],
        general_use_system=cfg["general_use_system"],
        general_reasoning=cfg["general_reasoning"],
        # Reasoning
        reasoning_model=cfg["reasoning_model"],
        reasoning_temp=cfg["reasoning_temp"],
        reasoning_max_tokens=cfg["reasoning_max_tokens"],
        reasoning_use_system=cfg["reasoning_use_system"],
        reasoning_reasoning=cfg["reasoning_reasoning"],
        # Casual
        casual_model=cfg["casual_model"],
        casual_temp=cfg["casual_temp"],
        casual_max_tokens=cfg["casual_max_tokens"],
        casual_use_system=cfg["casual_use_system"],
        casual_reasoning=cfg["casual_reasoning"],
        # Network
        request_timeout=cfg["request_timeout"],
        retry_count=cfg["retry_count"],
        retry_backoff=cfg["retry_backoff"],
    )

def _save_config_to_env_(cfg):
    """Persist all configuration keys to the .env file."""
    env_file = ".env"
    env_map = {
        "OPENROUTER_API_KEY":   cfg["api_key"],
        "TRIAGE_MODEL":         cfg["triage_model"],
        "TRIAGE_TEMP":          str(cfg["triage_temp"]),
        "TRIAGE_MAX_TOKENS":    str(cfg["triage_max_tokens"]),
        "TRIAGE_USE_SYSTEM":    str(cfg["triage_use_system"]),
        "TRIAGE_REASONING":     str(cfg["triage_reasoning"]),
        "ROUTER_MODEL":         cfg["router_model"],
        "ROUTER_TEMP":          str(cfg["router_temp"]),
        "ROUTER_MAX_TOKENS":    str(cfg["router_max_tokens"]),
        "ROUTER_USE_SYSTEM":    str(cfg["router_use_system"]),
        "ROUTER_REASONING":     str(cfg["router_reasoning"]),
        "GENERAL_MODEL":        cfg["general_model"],
        "GENERAL_TEMP":         str(cfg["general_temp"]),
        "GENERAL_MAX_TOKENS":   str(cfg["general_max_tokens"]),
        "GENERAL_USE_SYSTEM":   str(cfg["general_use_system"]),
        "GENERAL_REASONING":    str(cfg["general_reasoning"]),
        "REASONING_MODEL":      cfg["reasoning_model"],
        "REASONING_TEMP":       str(cfg["reasoning_temp"]),
        "REASONING_MAX_TOKENS": str(cfg["reasoning_max_tokens"]),
        "REASONING_USE_SYSTEM": str(cfg["reasoning_use_system"]),
        "REASONING_REASONING":  str(cfg["reasoning_reasoning"]),
        "CASUAL_MODEL":         cfg["casual_model"],
        "CASUAL_TEMP":          str(cfg["casual_temp"]),
        "CASUAL_MAX_TOKENS":    str(cfg["casual_max_tokens"]),
        "CASUAL_USE_SYSTEM":    str(cfg["casual_use_system"]),
        "CASUAL_REASONING":     str(cfg["casual_reasoning"]),
        "REQUEST_TIMEOUT":      str(cfg["request_timeout"]),
        "RETRY_COUNT":          str(cfg["retry_count"]),
        "RETRY_BACKOFF":        str(cfg["retry_backoff"]),
    }
    try:
        for key, value in env_map.items():
            set_key(env_file, key, value)
        print(f"  {GREEN}✓ All settings saved to .env{RESET}")
    except Exception as e:
        print(f"  {RED}✗ Could not save to .env: {e}{RESET}")

# ═══════════════════════════════════════════════════════════════
# 3. MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════
def main():
    clear_screen()
    print_banner()

    if "--fast" not in sys.argv:
        interactive_config()
    else:
        cfg = _load_config_from_env_()
        _apply_config_(cfg)

    clear_screen()
    print_banner()
    print(f"\n  {YELLOW}⏳ Initializing Adaptive Routing Framework...{RESET}\n")
    
    try:
        print(f"  {DIM}Loading Triage Module...{RESET}")
        triage = TriageModule()
        print_status_box("Triage Module", "Loaded", GREEN)

        print(f"  {DIM}Loading Semantic Router...{RESET}")
        router = SemanticRouterModule()
        print_status_box("Semantic Router", "Loaded", GREEN)

        print(f"  {DIM}Loading Legal Retrieval (FAISS)...{RESET}")
        retrieval = LegalRetrievalModule(
            index_path="localfiles/legal-basis/combined_index.faiss",
            chunks_path="localfiles/legal-basis/combined_index.json"
        )
        print_status_box("Legal Retrieval", "Loaded", GREEN)

    except Exception as e:
        print_error_box(
            "Initialization Failed",
            str(e),
            hint="Check that all model names are valid, the API key is set, and FAISS index files exist in localfiles/legal-basis/."
        )
        logging.error(f"Initialization failed: {e}")
        input(f"\n  Press Enter to exit...")
        sys.exit(1)

    history = []

    # --- Active Config Summary ---
    print_section_header("ACTIVE CONFIGURATION")
    print(f"  {'Triage:':<12} {CYAN}{FrameworkConfig._TRIAGE_MODEL}{RESET}  │  Sys: {_bool_str_(FrameworkConfig._TRIAGE_USE_SYSTEM)}  Reas: {_bool_str_(FrameworkConfig._TRIAGE_REASONING)}")
    print(f"  {'Router:':<12} {CYAN}{FrameworkConfig._ROUTER_MODEL}{RESET}  │  Sys: {_bool_str_(FrameworkConfig._ROUTER_USE_SYSTEM)}  Reas: {_bool_str_(FrameworkConfig._ROUTER_REASONING)}")
    print(f"  {'General:':<12} {CYAN}{FrameworkConfig._GENERAL_MODEL}{RESET}  │  Sys: {_bool_str_(FrameworkConfig._GENERAL_USE_SYSTEM)}  Reas: {_bool_str_(FrameworkConfig._GENERAL_REASONING)}")
    print(f"  {'Reasoning:':<12} {CYAN}{FrameworkConfig._REASONING_MODEL}{RESET}  │  Sys: {_bool_str_(FrameworkConfig._REASONING_USE_SYSTEM)}  Reas: {_bool_str_(FrameworkConfig._REASONING_REASONING)}")
    print(f"  {'Casual:':<12} {CYAN}{FrameworkConfig._CASUAL_MODEL}{RESET}  │  Sys: {_bool_str_(FrameworkConfig._CASUAL_USE_SYSTEM)}  Reas: {_bool_str_(FrameworkConfig._CASUAL_REASONING)}")

    # --- Ready ---
    print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════════╗
║              LEGAL ASSISTANT READY                   ║
╠══════════════════════════════════════════════════════╣{RESET}
║  Type {BOLD}'exit'{RESET} or {BOLD}'quit'{RESET}  to end the session.             ║
║  Type {BOLD}'clear'{RESET}          to clear conversation history. ║
║  Type {BOLD}'config'{RESET}         to view current configuration. ║{GREEN}{BOLD}
╚══════════════════════════════════════════════════════╝{RESET}
""")

    while True:
        try:
            user_input = input(f"\n{BOLD}👤 User:{RESET} ").strip()
            if not user_input:
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                print(f"\n  {YELLOW}Goodbye! 👋{RESET}\n")
                break

            if user_input.lower() == 'clear':
                history = []
                clear_screen()
                print_banner()
                print(f"  {GREEN}✓ Conversation history cleared.{RESET}\n")
                continue

            if user_input.lower() == 'config':
                print_section_header("CURRENT CONFIGURATION")
                print(f"  {'Triage:':<12} {FrameworkConfig._TRIAGE_MODEL}  (temp={FrameworkConfig._TRIAGE_TEMP}, tokens={FrameworkConfig._TRIAGE_MAX_TOKENS}, sys={FrameworkConfig._TRIAGE_USE_SYSTEM}, reas={FrameworkConfig._TRIAGE_REASONING})")
                print(f"  {'Router:':<12} {FrameworkConfig._ROUTER_MODEL}  (temp={FrameworkConfig._ROUTER_TEMP}, tokens={FrameworkConfig._ROUTER_MAX_TOKENS}, sys={FrameworkConfig._ROUTER_USE_SYSTEM}, reas={FrameworkConfig._ROUTER_REASONING})")
                print(f"  {'General:':<12} {FrameworkConfig._GENERAL_MODEL}  (temp={FrameworkConfig._GENERAL_TEMP}, tokens={FrameworkConfig._GENERAL_MAX_TOKENS}, sys={FrameworkConfig._GENERAL_USE_SYSTEM}, reas={FrameworkConfig._GENERAL_REASONING})")
                print(f"  {'Reasoning:':<12} {FrameworkConfig._REASONING_MODEL}  (temp={FrameworkConfig._REASONING_TEMP}, tokens={FrameworkConfig._REASONING_MAX_TOKENS}, sys={FrameworkConfig._REASONING_USE_SYSTEM}, reas={FrameworkConfig._REASONING_REASONING})")
                print(f"  {'Casual:':<12} {FrameworkConfig._CASUAL_MODEL}  (temp={FrameworkConfig._CASUAL_TEMP}, tokens={FrameworkConfig._CASUAL_MAX_TOKENS}, sys={FrameworkConfig._CASUAL_USE_SYSTEM}, reas={FrameworkConfig._CASUAL_REASONING})")
                print(f"  {'Network:':<12} timeout={FrameworkConfig._REQUEST_TIMEOUT}s, retries={FrameworkConfig._RETRY_COUNT}, backoff={FrameworkConfig._RETRY_BACKOFF}s")
                print()
                continue

            # ──────────────────────────────────────────────────
            # Stage 1: Triage (Normalization)
            # ──────────────────────────────────────────────────
            triage_result = None
            detected_language = "Unknown"
            normalized_text = user_input
            
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    triage_result = triage._process_request_(user_input)
                    normalized_text = triage_result.get("normalized_text", user_input)
                    detected_language = triage_result.get("detected_language", "Unknown")
                    if triage_result.get("error"):
                        raise Exception(triage_result["error"])
                    break
                except Exception as e:
                    logging.error(f"Triage error on attempt {attempt}: {e}")
                    if _is_rate_limited_(e) and attempt < MAX_RETRIES:
                        delay = BASE_DELAY * attempt
                        print(f"  {YELLOW}⏳ [Triage] Rate-limited. Retrying in {delay}s (attempt {attempt}/{MAX_RETRIES})...{RESET}")
                        time.sleep(delay)
                    else:
                        print_error_box(
                            "Triage Failed",
                            f"Could not normalize text after {attempt} attempts: {e}",
                            hint="Using raw input as fallback. If this persists, check TRIAGE_MODEL and TRIAGE_USE_SYSTEM settings."
                        )
                        break

            logging.info(f"[Triage] language={detected_language!r} normalized={normalized_text!r}")
            print(f"\n  {CYAN}⚙️  Triage{RESET}  │  Language: {BOLD}{detected_language}{RESET}")
            print(f"  {'':>10} │  Normalized: {DIM}{normalized_text}{RESET}")

            # ──────────────────────────────────────────────────
            # Stage 2: Semantic Routing (Classification)
            # ──────────────────────────────────────────────────
            classification = {"route": "General-LLM", "confidence": 0.0, "trigger_signals": []}
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    result = router._process_routing_(normalized_text, threshold=0.1, persistence_level=MAX_RETRIES)
                    logging.info(f"[Router Raw Output] {result}")
                    
                    if result.get("error"):
                        if result.get("error") == "LLMEngine failed to acknowledge the input.":
                            classification = {
                                "route": "Casual-LLM",
                                "confidence": 1.0,
                                "trigger_signals": ["Fallback due to threshold failure"]
                            }
                            break
                        else:
                            raise Exception(result["error"])
                    classification = result
                    break
                except Exception as e:
                    logging.error(f"Routing error on attempt {attempt}: {e}")
                    if _is_rate_limited_(e) and attempt < MAX_RETRIES:
                        delay = BASE_DELAY * attempt
                        print(f"  {YELLOW}⏳ [Router] Rate-limited. Retrying in {delay}s (attempt {attempt}/{MAX_RETRIES})...{RESET}")
                        time.sleep(delay)
                    else:
                        print_error_box(
                            "Routing Failed",
                            f"Could not classify route after {attempt} attempts: {e}",
                            hint=(
                                "Defaulting to General-LLM. Common fixes:\n"
                                "  • Set ROUTER_USE_SYSTEM=True if model ignores merged prompts.\n"
                                "  • Set ROUTER_REASONING=False if model lacks reasoning support.\n"
                                "  • Check if the free-tier model is rate-limited."
                            )
                        )
                        break

            route = classification.get("route", "General-LLM")
            confidence = classification.get("confidence", 0.0)
            signals = classification.get("trigger_signals", [])
            logging.info(f"[Router] route={route!r} confidence={confidence:.2f} signals={signals}")

            # Color-code the route
            route_colors = {"Reasoning-LLM": MAGENTA, "General-LLM": BLUE, "Casual-LLM": YELLOW}
            rc = route_colors.get(route, WHITE)
            print(f"  {MAGENTA}🔀 Router{RESET}  │  Route: {rc}{BOLD}{route}{RESET}  (Confidence: {confidence:.2f})")
            if signals:
                print(f"  {'':>10} │  Signals: {DIM}{', '.join(str(s) for s in signals)}{RESET}")

            # ──────────────────────────────────────────────────
            # Stage 3: RAG Retrieval (skip for Casual)
            # ──────────────────────────────────────────────────
            context_str = None
            if route != "Casual-LLM":
                try:
                    retrieval_output = retrieval._process_retrieval_(normalized_text)
                    chunks = retrieval_output.get("retrieved_chunks", [])
                    if chunks:
                        context_str = "\n\n".join([c.get("chunk", "") for c in chunks[:3]])
                        print(f"  {GREEN}📚 RAG{RESET}     │  Retrieved {BOLD}{len(chunks[:3])}{RESET} relevant legal sources.")
                    else:
                        print(f"  {DIM}📚 RAG     │  No relevant sources found.{RESET}")
                except Exception as e:
                    logging.error(f"Retrieval error: {e}")
                    print_error_box(
                        "RAG Retrieval Failed",
                        str(e),
                        hint="Proceeding without legal context. Ensure FAISS index files are present in localfiles/legal-basis/."
                    )

            # ──────────────────────────────────────────────────
            # Stage 4: Generation (Multi-Turn)
            # ──────────────────────────────────────────────────
            # Add the user's message to history BEFORE generation so the API always has messages
            history.append({"role": "user", "content": normalized_text})

            print(f"\n  {DIM}🤖 Generating response...{RESET}")
            response = ""
            accepted = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    gen_result = router._generate_conversation_(
                        classification=classification,
                        messages=history,
                        context=context_str
                    )
                    if gen_result.get("error"):
                        raise Exception(gen_result["error"])
                    raw_response = gen_result.get("response_text")
                    logging.info(f"[Generation] attempt={attempt} raw_response_type={type(raw_response).__name__!r} raw_response_value={raw_response!r}")
                    response = raw_response or "No response generated."
                    accepted = gen_result.get("accepted", True)
                    break
                except Exception as e:
                    logging.error(f"Generation error on attempt {attempt}: {e}")
                    if _is_rate_limited_(e) and attempt < MAX_RETRIES:
                        delay = BASE_DELAY * attempt
                        print(f"  {YELLOW}⏳ [Generator] Rate-limited. Retrying in {delay}s (attempt {attempt}/{MAX_RETRIES})...{RESET}")
                        time.sleep(delay)
                    else:
                        print_error_box(
                            "Generation Failed",
                            f"Could not generate response after {attempt} attempts: {e}",
                            hint="Check cli_errors.log for full error details. The model may be rate-limited or misconfigured."
                        )
                        response = "I am currently unable to process your query due to a technical error. Please check cli_errors.log."
                        accepted = False
                        break

            # Update history with the assistant's response
            history.append({"role": "assistant", "content": response})

            # ──────────────────────────────────────────────────
            # Output
            # ──────────────────────────────────────────────────
            if accepted:
                status_line = f"{GREEN}{BOLD}✓ Accepted{RESET}"
            else:
                status_line = f"{RED}{BOLD}✗ Requires Review / Error{RESET}"

            print(f"\n{BLUE}╔══════════════════════════════════════════════════════╗{RESET}")
            print(f"{BLUE}║{RESET}  Status: {status_line}{'':>20}{BLUE}║{RESET}")
            print(f"{BLUE}╠══════════════════════════════════════════════════════╣{RESET}")
            print(f"{BLUE}║{RESET}  {BOLD}RESPONSE{RESET}{'':>46}{BLUE}║{RESET}")
            print(f"{BLUE}╠══════════════════════════════════════════════════════╣{RESET}")
            # Print response with left padding
            for line in response.split('\n'):
                print(f"  {line}")
            print(f"{BLUE}╚══════════════════════════════════════════════════════╝{RESET}\n")

        except KeyboardInterrupt:
            print(f"\n\n  {YELLOW}Goodbye! 👋{RESET}\n")
            break
        except Exception as e:
            logging.error(f"Unexpected main loop error: {e}")
            print_error_box(
                "Unexpected Error",
                str(e),
                hint="See cli_errors.log for full stack trace."
            )

if __name__ == "__main__":
    main()
