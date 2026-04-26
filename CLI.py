import os
import sys

# Ensure CWD is always the project root so paths and logs are correct even if spawned from IDEs or Applescript
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)

import platform
import subprocess
import time
import logging
import json
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
for noisy in ('urllib3', 'requests', 'charset_normalizer', 'faiss', 'urllib3.connectionpool'):
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
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.live import Live
from rich import print as rprint
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle

# ═══════════════════════════════════════════════════════════════
# 1. UI HELPERS (RICH)
# ═══════════════════════════════════════════════════════════════

console = Console()

def clear_screen():
    console.clear()

def print_banner():
    banner_text = """[cyan]
  _       __  __  ____  _____ 
 | |     / _ \\|  _ \\|  ___|
 | |    | |_| | |_) | |_   
 | |___ |  _  |  _ <|  _|  
 |_____||_| |_|_| \\_\\_|  
[/cyan]
[yellow]Legal Adaptive Routing Framework[/yellow]
[yellow]Philippine & Hong Kong Legal Queries[/yellow]
"""
    panel = Panel(banner_text, title="[blue]404FoundUs | Saint Louis University[/blue]", border_style="blue", expand=False)
    console.print(panel)

def print_section_header(title, color="cyan"):
    console.print(f"\n[bold {color}]──── {title} {'─' * (53 - len(title))}[/]")

def print_error_box(stage, message, hint=None):
    """Print a formatted error box with optional config hint."""
    error_text = f"[red]✗ ERROR: {stage}[/red]\n{message}"
    if hint:
        error_text += f"\n\n[yellow bold]💡 Hint:[/yellow bold] [yellow]{hint}[/yellow]"
    console.print(Panel(error_text, border_style="red", title="[bold red]Error[/]"))

def print_status_box(label, value, color="green"):
    """Print a small inline status indicator."""
    icon = "✓" if color == "green" else "⚠" if color == "yellow" else "✗"
    console.print(f"  [{color}]{icon}[/] {label}: [{color}]{value}[/]")

def _bool_str_(val):
    if val:
        return "[green]ON[/green]"
    return "[red]OFF[/red]"

def _input_bool_(prompt, current):
    """Prompt user for a boolean toggle (on/off)."""
    display = "ON" if current else "OFF"
    val = console.input(f"  {prompt} (currently {display}) [on/off/skip]: ").strip().lower()
    if val in ('on', 'true', 'yes', '1'):
        return True
    elif val in ('off', 'false', 'no', '0'):
        return False
    return current

def _input_float_(prompt, current):
    val = console.input(f"  {prompt} (currently {current}): ").strip()
    if not val:
        return current
    try:
        return float(val)
    except ValueError:
        console.print(f"  [red]Invalid number. Keeping {current}.[/red]")
        return current

def _input_int_(prompt, current):
    val = console.input(f"  {prompt} (currently {current}): ").strip()
    if not val:
        return current
    try:
        return int(val)
    except ValueError:
        console.print(f"  [red]Invalid number. Keeping {current}.[/red]")
        return current

# ═══════════════════════════════════════════════════════════════
# 2. CONFIGURATION MENU (Complete)
# ═══════════════════════════════════════════════════════════════

_config = {}

def _load_config_from_env_():
    load_dotenv()
    return {
        "api_key":              FrameworkConfig._API_KEY,
        "triage_model":         FrameworkConfig._TRIAGE_MODEL,
        "triage_temp":          FrameworkConfig._TRIAGE_TEMP,
        "triage_max_tokens":    FrameworkConfig._TRIAGE_MAX_TOKENS,
        "triage_use_system":    FrameworkConfig._TRIAGE_USE_SYSTEM,
        "triage_reasoning":     FrameworkConfig._TRIAGE_REASONING,
        "triage_instructions":  FrameworkConfig._TRIAGE_INSTRUCTIONS,
        "router_model":         FrameworkConfig._ROUTER_MODEL,
        "router_temp":          FrameworkConfig._ROUTER_TEMP,
        "router_max_tokens":    FrameworkConfig._ROUTER_MAX_TOKENS,
        "router_use_system":    FrameworkConfig._ROUTER_USE_SYSTEM,
        "router_reasoning":     FrameworkConfig._ROUTER_REASONING,
        "general_model":        FrameworkConfig._GENERAL_MODEL,
        "general_temp":         FrameworkConfig._GENERAL_TEMP,
        "general_max_tokens":   FrameworkConfig._GENERAL_MAX_TOKENS,
        "general_use_system":   FrameworkConfig._GENERAL_USE_SYSTEM,
        "general_reasoning":    FrameworkConfig._GENERAL_REASONING,
        "general_instructions": FrameworkConfig._GENERAL_INSTRUCTIONS,
        "reasoning_model":      FrameworkConfig._REASONING_MODEL,
        "reasoning_temp":       FrameworkConfig._REASONING_TEMP,
        "reasoning_max_tokens": FrameworkConfig._REASONING_MAX_TOKENS,
        "reasoning_use_system": FrameworkConfig._REASONING_USE_SYSTEM,
        "reasoning_reasoning":  FrameworkConfig._REASONING_REASONING,
        "reasoning_instructions": FrameworkConfig._REASONING_INSTRUCTIONS,
        "casual_model":         FrameworkConfig._CASUAL_MODEL,
        "casual_temp":          FrameworkConfig._CASUAL_TEMP,
        "casual_max_tokens":    FrameworkConfig._CASUAL_MAX_TOKENS,
        "casual_use_system":    FrameworkConfig._CASUAL_USE_SYSTEM,
        "casual_reasoning":     FrameworkConfig._CASUAL_REASONING,
        "casual_instructions":  FrameworkConfig._CASUAL_INSTRUCTIONS,
        "request_timeout":      FrameworkConfig._REQUEST_TIMEOUT,
        "retry_count":          FrameworkConfig._RETRY_COUNT,
        "retry_backoff":        FrameworkConfig._RETRY_BACKOFF,
    }

def _edit_module_config_(name, cfg, prefix):
    console.print(f"\n[cyan bold]  Editing: {name}[/]")
    console.print("[dim]──────────────────────────────────────────────────[/]")
    cfg[f"{prefix}_model"] = console.input(f"  Model (currently {cfg[f'{prefix}_model']}): ").strip() or cfg[f"{prefix}_model"]
    cfg[f"{prefix}_temp"] = _input_float_("Temperature", cfg[f"{prefix}_temp"])
    cfg[f"{prefix}_max_tokens"] = _input_int_("Max Tokens", cfg[f"{prefix}_max_tokens"])
    cfg[f"{prefix}_use_system"] = _input_bool_("System Role", cfg[f"{prefix}_use_system"])
    cfg[f"{prefix}_reasoning"] = _input_bool_("Reasoning", cfg[f"{prefix}_reasoning"])
    console.print(f"  [green]✓ {name} configuration updated.[/green]")

def _import_config_file_(cfg):
    console.print(f"\n[cyan bold]  Import .config File[/cyan bold]")
    console.print("[dim]──────────────────────────────────────────────────[/]")
    filepath = console.input("  Enter path to .config file (e.g. localfiles/stable_veritas_v1.config): ").strip()
    if not filepath:
        console.print("  [yellow]Import cancelled.[/yellow]")
        return
    if not os.path.exists(filepath):
        console.print(f"  [red]✗ File not found: {filepath}[/red]")
        return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        config_data = data.get("config", {})
        
        module_map = {
            "triage": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "router": ["model", "temp", "max_tokens", "use_system", "reasoning"],
            "general": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "reasoning": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "casual": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
        }
        
        updates = 0
        for module, fields in module_map.items():
            if module in config_data:
                for field in fields:
                    if field in config_data[module]:
                        key = f"{module}_{field}"
                        val = config_data[module][field]
                        if field == "temp": val = float(val)
                        elif field == "max_tokens": val = int(val)
                        elif field in ("use_system", "reasoning"): val = bool(val)
                        if key in cfg:
                            cfg[key] = val
                            updates += 1
                            
        console.print(f"  [green]✓ Successfully imported {updates} settings from {filepath}[/green]")
    except Exception as e:
        console.print(f"  [red]✗ Failed to import config: {e}[/red]")

def interactive_config():
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
        
        key_status = "[green][SET][/green]" if _config["api_key"] else "[red][NOT SET][/red]"
        console.print(f"\n  [bold]0.[/bold] API Key: {key_status}\n")
        
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Opt", style="dim", width=4)
        table.add_column("Module", width=18)
        table.add_column("Model", style="cyan", width=30)
        table.add_column("Sys", width=8)
        table.add_column("Reas", width=8)

        for i, (name, prefix) in enumerate(modules, 1):
            sys_status = _bool_str_(_config[f"{prefix}_use_system"])
            reas_status = _bool_str_(_config[f"{prefix}_reasoning"])
            model = _config[f"{prefix}_model"]
            table.add_row(f"{i}.", name, model, sys_status, reas_status)
            
        console.print(table)
        console.print()
        console.print(f"  [bold]6.[/bold] Network Settings   │ Timeout: {_config['request_timeout']}s  Retries: {_config['retry_count']}  Backoff: {_config['retry_backoff']}s")
        
        console.print("\n[dim]──────────────────────────────────────────────────[/]")
        console.print("  [bold]I.[/bold] Import .config File")
        console.print("  [bold]S.[/bold] Save and Start Chat")
        console.print("  [bold]Q.[/bold] Quit")
        
        choice = console.input("\n  Select option (0-6, I, S, Q): ").strip().upper()
        
        if choice == '0':
            _config["api_key"] = console.input("  Enter OpenRouter API Key: ").strip() or _config["api_key"]
        elif choice in ('1', '2', '3', '4', '5'):
            idx = int(choice) - 1
            name, prefix = modules[idx]
            _edit_module_config_(name, _config, prefix)
            console.input("\n  Press Enter to continue...")
        elif choice == '6':
            console.print(f"\n[cyan bold]  Editing: Network Settings[/cyan bold]")
            console.print("[dim]──────────────────────────────────────────────────[/]")
            _config["request_timeout"] = _input_int_("Request Timeout (seconds)", _config["request_timeout"])
            _config["retry_count"] = _input_int_("Retry Count", _config["retry_count"])
            _config["retry_backoff"] = _input_float_("Retry Backoff (seconds)", _config["retry_backoff"])
            console.print("  [green]✓ Network settings updated.[/green]")
            console.input("\n  Press Enter to continue...")
        elif choice == 'I':
            _import_config_file_(_config)
            console.input("\n  Press Enter to continue...")
        elif choice == 'S':
            break
        elif choice == 'Q':
            console.print("\n  [yellow]Exiting...[/yellow]")
            sys.exit(0)

    _apply_config_(_config)
    save_ans = console.input("\n  Save configuration to .env? (y/n): ").strip().lower()
    if save_ans == 'y':
        _save_config_to_env_(_config)

def _apply_config_(cfg):
    FrameworkConfig._update_settings_(
        api_key=cfg["api_key"],
        triage_model=cfg["triage_model"],
        triage_temp=cfg["triage_temp"],
        triage_max_tokens=cfg["triage_max_tokens"],
        triage_use_system=cfg["triage_use_system"],
        triage_reasoning=cfg["triage_reasoning"],
        triage_instructions=cfg.get("triage_instructions"),
        router_model=cfg["router_model"],
        router_temp=cfg["router_temp"],
        router_max_tokens=cfg["router_max_tokens"],
        router_use_system=cfg["router_use_system"],
        router_reasoning=cfg["router_reasoning"],
        general_model=cfg["general_model"],
        general_temp=cfg["general_temp"],
        general_max_tokens=cfg["general_max_tokens"],
        general_use_system=cfg["general_use_system"],
        general_reasoning=cfg["general_reasoning"],
        general_instructions=cfg.get("general_instructions"),
        reasoning_model=cfg["reasoning_model"],
        reasoning_temp=cfg["reasoning_temp"],
        reasoning_max_tokens=cfg["reasoning_max_tokens"],
        reasoning_use_system=cfg["reasoning_use_system"],
        reasoning_reasoning=cfg["reasoning_reasoning"],
        reasoning_instructions=cfg.get("reasoning_instructions"),
        casual_model=cfg["casual_model"],
        casual_temp=cfg["casual_temp"],
        casual_max_tokens=cfg["casual_max_tokens"],
        casual_use_system=cfg["casual_use_system"],
        casual_reasoning=cfg["casual_reasoning"],
        casual_instructions=cfg.get("casual_instructions"),
        request_timeout=cfg["request_timeout"],
        retry_count=cfg["retry_count"],
        retry_backoff=cfg["retry_backoff"],
    )

def _save_config_to_env_(cfg):
    env_file = ".env"
    env_map = {
        "OPENROUTER_API_KEY":   cfg["api_key"],
        "TRIAGE_MODEL":         cfg["triage_model"],
        "TRIAGE_TEMP":          str(cfg["triage_temp"]),
        "TRIAGE_MAX_TOKENS":    str(cfg["triage_max_tokens"]),
        "TRIAGE_USE_SYSTEM":    str(cfg["triage_use_system"]),
        "TRIAGE_REASONING":     str(cfg["triage_reasoning"]),
        "TRIAGE_INSTRUCTIONS":  cfg.get("triage_instructions", ""),
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
        "GENERAL_INSTRUCTIONS": cfg.get("general_instructions", ""),
        "REASONING_MODEL":      cfg["reasoning_model"],
        "REASONING_TEMP":       str(cfg["reasoning_temp"]),
        "REASONING_MAX_TOKENS": str(cfg["reasoning_max_tokens"]),
        "REASONING_USE_SYSTEM": str(cfg["reasoning_use_system"]),
        "REASONING_REASONING":  str(cfg["reasoning_reasoning"]),
        "REASONING_INSTRUCTIONS": cfg.get("reasoning_instructions", ""),
        "CASUAL_MODEL":         cfg["casual_model"],
        "CASUAL_TEMP":          str(cfg["casual_temp"]),
        "CASUAL_MAX_TOKENS":    str(cfg["casual_max_tokens"]),
        "CASUAL_USE_SYSTEM":    str(cfg["casual_use_system"]),
        "CASUAL_REASONING":     str(cfg["casual_reasoning"]),
        "CASUAL_INSTRUCTIONS":  cfg.get("casual_instructions", ""),
        "REQUEST_TIMEOUT":      str(cfg["request_timeout"]),
        "RETRY_COUNT":          str(cfg["retry_count"]),
        "RETRY_BACKOFF":        str(cfg["retry_backoff"]),
    }
    try:
        for key, value in env_map.items():
            set_key(env_file, key, value)
        console.print("  [green]✓ All settings saved to .env[/green]")
    except Exception as e:
        console.print(f"  [red]✗ Could not save to .env: {e}[/red]")

# ═══════════════════════════════════════════════════════════════
# 3. COMMAND HELPERS
# ═══════════════════════════════════════════════════════════════
def print_help():
    table = Table(title="Available Commands", box=None, show_lines=False, header_style="bold magenta")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")
    table.add_row("-help", "Show this help message")
    table.add_row("-config", "Enter configuration menu")
    table.add_row("-reindex", "Rebuild the legal FAISS index")
    table.add_row("-clear", "Clear console and conversation history")
    table.add_row("-exit", "Exit the assistant")
    console.print()
    console.print(table)
    console.print()

def print_active_config():
    print_section_header("ACTIVE CONFIGURATION")
    table = Table(box=None, header_style="bold magenta")
    table.add_column("Module", width=12)
    table.add_column("Model", style="cyan")
    table.add_column("Settings", style="dim")
    
    table.add_row("Triage:", FrameworkConfig._TRIAGE_MODEL, f"Sys: {_bool_str_(FrameworkConfig._TRIAGE_USE_SYSTEM)} Reas: {_bool_str_(FrameworkConfig._TRIAGE_REASONING)}")
    table.add_row("Router:", FrameworkConfig._ROUTER_MODEL, f"Sys: {_bool_str_(FrameworkConfig._ROUTER_USE_SYSTEM)} Reas: {_bool_str_(FrameworkConfig._ROUTER_REASONING)}")
    table.add_row("General:", FrameworkConfig._GENERAL_MODEL, f"Sys: {_bool_str_(FrameworkConfig._GENERAL_USE_SYSTEM)} Reas: {_bool_str_(FrameworkConfig._GENERAL_REASONING)}")
    table.add_row("Reasoning:", FrameworkConfig._REASONING_MODEL, f"Sys: {_bool_str_(FrameworkConfig._REASONING_USE_SYSTEM)} Reas: {_bool_str_(FrameworkConfig._REASONING_REASONING)}")
    table.add_row("Casual:", FrameworkConfig._CASUAL_MODEL, f"Sys: {_bool_str_(FrameworkConfig._CASUAL_USE_SYSTEM)} Reas: {_bool_str_(FrameworkConfig._CASUAL_REASONING)}")
    console.print(table)
    console.print()

# ═══════════════════════════════════════════════════════════════
# 4. MAIN APPLICATION
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
    console.print("\n  [yellow]⏳ Initializing Adaptive Routing Framework...[/yellow]\n")
    
    try:
        with console.status("[dim]Loading Modules...[/dim]", spinner="dots"):
            triage = TriageModule()
            print_status_box("Triage Module", "Loaded", "green")

            router = SemanticRouterModule()
            print_status_box("Semantic Router", "Loaded", "green")

            retrieval = LegalRetrievalModule(
                index_path="localfiles/legal-basis/combined_index.faiss",
                chunks_path="localfiles/legal-basis/combined_index.json"
            )
            print_status_box("Legal Retrieval", "Loaded", "green")

            # Check sync status
            sync_info = legal_indexing.verify_index_integrity(
                corpus_dir="legal-corpus",
                chunks_path="localfiles/legal-basis/combined_index.json"
            )
            if not sync_info["is_synced"]:
                print_status_box(
                    "Index Sync", 
                    f"Out of Sync ({sync_info['missing_count']} missing)", 
                    "yellow"
                )
                console.print(f"    [yellow]Tip: Run [bold]-reindex[/bold] to update the knowledge base.[/yellow]")
            else:
                print_status_box("Index Sync", "Synced", "green")

    except Exception as e:
        print_error_box(
            "Initialization Failed",
            str(e),
            hint="Check that all model names are valid, the API key is set, and FAISS index files exist in localfiles/legal-basis/."
        )
        logging.error(f"Initialization failed: {e}")
        console.input("\n  Press Enter to exit...")
        sys.exit(1)

    history = []
    last_rag_context = None

    print_active_config()

    # --- Ready ---
    ready_msg = """
[bold]Type [cyan]-help[/cyan] for a list of commands.[/bold]
[dim]Send a message to start adapting routes...[/dim]
"""
    console.print(Panel(ready_msg, border_style="green", title="[bold green]LEGAL ASSISTANT READY[/]"))

    prompt_style = PromptStyle.from_dict({
        'prompt': 'bold #00ffff',
    })
    session = PromptSession()

    while True:
        try:
            console.print()
            user_input = session.prompt("👤 ❯ ", style=prompt_style).strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['-exit', '-quit', 'exit', 'quit']:
                console.print("\n  [yellow]Goodbye! 👋[/yellow]\n")
                break

            if user_input.lower() == '-help':
                print_help()
                continue
                
            if user_input.lower() == '-clear':
                history = []
                clear_screen()
                print_banner()
                console.print("  [green]✓ Conversation history cleared.[/green]\n")
                continue

            if user_input.lower() == '-config':
                interactive_config()
                clear_screen()
                print_banner()
                print_active_config()
                continue

            if user_input.lower() == '-reindex':
                with console.status("[bold yellow]Rebuilding Index... (This will take a while)[/]", spinner="bouncingBar"):
                    try:
                        legal_indexing.rebuild_index(
                            corpus_dir="legal-corpus",
                            output_dir="localfiles/legal-basis"
                        )
                        # Reload retrieval module with new index
                        retrieval = LegalRetrievalModule(
                            index_path="localfiles/legal-basis/combined_index.faiss",
                            chunks_path="localfiles/legal-basis/combined_index.json"
                        )
                        console.print("  [green]✓ Index rebuilt and reloaded successfully.[/green]")
                    except Exception as reindex_err:
                        print_error_box("Re-indexing Failed", str(reindex_err))
                continue

            # ──────────────────────────────────────────────────
            # Stage 1: Triage (Normalization)
            # ──────────────────────────────────────────────────
            triage_result = None
            detected_language = "Unknown"
            normalized_text = user_input
            
            with console.status("[cyan]⚙️  Triaging input...[/cyan]", spinner="dots"):
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
                            console.status(f"[yellow]⏳ [Triage] Rate-limited. Retrying... ({attempt}/{MAX_RETRIES})[/yellow]")
                            time.sleep(BASE_DELAY * attempt)
                        else:
                            console.print()
                            print_error_box("Triage Failed", f"{e}", hint="Using raw input as fallback.")
                            break

            logging.info(f"[Triage] language={detected_language!r} normalized={normalized_text!r}")
            # Display triage output compactly
            console.print(f"  [cyan]⚙️  Triage[/cyan]  │  [dim]Lang: {detected_language} | Normalized: {normalized_text}[/dim]")

            # ──────────────────────────────────────────────────
            # Stage 2: Semantic Routing (Classification)
            # ──────────────────────────────────────────────────
            classification = {"route": "General-LLM", "confidence": 0.0, "search_signals": None}
            with console.status("[magenta]🔀 Routing request...[/magenta]", spinner="dots"):
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        result = router._process_routing_(normalized_text, threshold=0.1, persistence_level=MAX_RETRIES)
                        logging.info(f"[Router Raw Output] {result}")
                        
                        if result.get("error"):
                            if result.get("error") == "LLMEngine failed to acknowledge the input.":
                                classification = {
                                    "route": "Casual-LLM",
                                    "confidence": 1.0,
                                    "search_signals": None
                                }
                                break
                            else:
                                raise Exception(result["error"])
                        classification = result
                        break
                    except Exception as e:
                        logging.error(f"Routing error on attempt {attempt}: {e}")
                        if _is_rate_limited_(e) and attempt < MAX_RETRIES:
                            console.status(f"[yellow]⏳ [Router] Rate-limited. Retrying... ({attempt}/{MAX_RETRIES})[/yellow]")
                            time.sleep(BASE_DELAY * attempt)
                        else:
                            console.print()
                            print_error_box("Routing Failed", f"{e}", hint="Defaulting to General-LLM.")
                            break

            route = classification.get("route", "General-LLM")
            confidence = classification.get("confidence", 0.0)
            signals = classification.get("search_signals")
            logging.info(f"[Router] route={route!r} confidence={confidence:.2f} signals={signals}")

            route_colors = {"Reasoning-LLM": "magenta", "General-LLM": "blue", "Casual-LLM": "yellow"}
            rc = route_colors.get(route, "white")
            signal_text = f" | [dim]Search Signals: {', '.join(str(s) for s in signals)}[/dim]" if signals else " | [dim]Follow-up Detection: REUSING CONTEXT[/dim]" if route != "Casual-LLM" else ""
            console.print(f"  [magenta]🔀 Router[/magenta]  │  Route: [{rc} bold]{route}[/] (Conf: {confidence:.2f}){signal_text}")

            # ──────────────────────────────────────────────────
            # Stage 3: RAG Retrieval (skip for Casual)
            # ──────────────────────────────────────────────────
            context_str = last_rag_context  # Initial fallback
            
            if route != "Casual-LLM":
                # Use search_signals to decide if we need a new search
                if signals is not None:
                    with console.status("[green]📚 Searching legal corpus (Hybrid BM25 + Vector)...[/green]", spinner="dots"):
                        try:
                            retrieval_output = retrieval._process_retrieval_(normalized_text, signals=signals)
                            chunks = retrieval_output.get("retrieved_chunks", [])
                            if chunks:
                                context_str = "\n\n".join([c.get("chunk", "") for c in chunks[:5]])
                                last_rag_context = context_str  # Update persistence
                                console.print(f"  [green]📚 RAG[/green]     │  New information found. Retrieved [bold]{len(chunks[:5])}[/bold] sources.")
                            else:
                                console.print(f"  [dim]📚 RAG[/dim]     │  [dim]No new relevant sources found.[/dim]")
                                context_str = None # Reset if truly nothing found on a new search
                        except Exception as e:
                            logging.error(f"Retrieval error: {e}")
                            console.print()
                            print_error_box("RAG Retrieval Failed", str(e), hint="Proceeding with fallback or no context.")
                else:
                    # Signals are null, reuse last context
                    if last_rag_context:
                        console.print(f"  [green]📚 RAG[/green]     │  [cyan]Context Reuse Mode[/cyan]: Reusing previous legal findings.")
                    else:
                        console.print(f"  [dim]📚 RAG[/dim]     │  [dim]No previous context to reuse.[/dim]")
            else:
                context_str = None # No context for casual routes

            # ──────────────────────────────────────────────────
            # Stage 4: Generation (Multi-Turn)
            # ──────────────────────────────────────────────────
            history.append({"role": "user", "content": normalized_text})

            response = ""
            accepted = False
            with console.status("[dim]🤖 Generating response...[/dim]", spinner="bouncingBar"):
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        gen_result = router._generate_conversation_(
                            classification=classification,
                            messages=history,
                            context=context_str,
                            is_follow_up=(signals is None and route != "Casual-LLM")
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
                            console.status(f"[yellow]⏳ [Generator] Rate-limited. Retrying... ({attempt}/{MAX_RETRIES})[/yellow]")
                            time.sleep(BASE_DELAY * attempt)
                        else:
                            console.print()
                            print_error_box("Generation Failed", str(e), hint="Check cli_errors.log for full details.")
                            response = "I am currently unable to process your query due to a technical error."
                            accepted = False
                            break

            history.append({"role": "assistant", "content": response})

            # ──────────────────────────────────────────────────
            # Output
            # ──────────────────────────────────────────────────
            status_line = "[green bold]✓ Accepted[/]" if accepted else "[red bold]✗ Requires Review / Error[/]"
            
            md_response = Markdown(response)
            
            panel = Panel(
                md_response,
                title=f"[cyan]Response[/] - {status_line}",
                border_style="blue",
                padding=(1, 2)
            )
            console.print()
            console.print(panel)

        except KeyboardInterrupt:
            console.print("\n\n  [yellow]Goodbye! 👋[/yellow]\n")
            break
        except Exception as e:
            logging.error(f"Unexpected main loop error: {e}")
            console.print()
            print_error_box("Unexpected Error", str(e), hint="See cli_errors.log for full stack trace.")

if __name__ == "__main__":
    main()
