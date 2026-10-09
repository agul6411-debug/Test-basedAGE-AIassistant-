"""Layer 1 Rule and Keyword Command Router.

Security Rule 3:
LLM and transcribed speech are untrusted input.
All parameters are sanitized and strictly validated against Pydantic schemas.
"""

import random
import re
from typing import Any

from pydantic import BaseModel, Field

from core.brain.groq_client import GroqClient, GroqClientError
from core.brain.ollama_client import OFFLINE_MESSAGE, OllamaClient

from core.logger import get_logger
from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.tools.registry import registry

logger = get_logger("brain.router")

MAX_INPUT_LENGTH = 1000


APP_ALIASES: dict[str, str] = {
    "calculator": "calc",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "google chrome": "chrome",
    "google": "chrome",
    "browser": "chrome",
    "chrom": "chrome",
    "chromee": "chrome",
    "internet": "chrome",
    "web": "chrome",
    "microsoft edge": "edge",
    "file explorer": "explorer",
    "files": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "word": "word",
    "ms word": "word",
    "microsoft word": "word",
    "doc": "word",
    "docs": "word",
    "excel": "excel",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "sheets": "excel",
    "powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "ms powerpoint": "powerpoint",
    "slides": "powerpoint",
    "presentation": "powerpoint",
    "power point": "powerpoint",
    "paint": "paint",
    "ms paint": "paint",
    "drawing": "paint",
    "onenote": "onenote",
    "outlook": "outlook",
    "mail": "outlook",
    "email": "outlook",
    "access": "access",
    "ms access": "access",
    "task manager": "taskmanager",
    "tasks": "taskmanager",
    "control panel": "controlpanel",
    "settings": "controlpanel",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "screenshot": "snippingtool",
    "media player": "media",
    "music": "media",
    "player": "media",
    "downloads": "downloads",
    "download": "downloads",
    "downloads folder": "downloads",
    "my downloads": "downloads",
    "documents": "documents",
    "documents folder": "documents",
    "my documents": "documents",
    "desktop": "desktop",
    "desktop folder": "desktop",
    "my desktop": "desktop",
    "pictures": "pictures",
    "pictures folder": "pictures",
    "my pictures": "pictures",
    "photos": "pictures",
    "videos": "videos",
    "videos folder": "videos",
    "c drive": "c drive",
}

PRONOUNS_AND_VAGUE: set[str] = {
    "it", "this", "that", "the app", "app", "application", "file", "folder",
    "something", "anything", "isay", "isko", "usko", "ye", "yeh", "wo", "woh",
}

ROBOT_JOKES: list[str] = [
    "Teacher: Batao sab se bara parinda konsa hai? Pappu: Sir, hawai jahaz! Teacher: Aur sab se tezi se udnay wala? Pappu: Hawai jahaz ke peechay laga hua ticket-checker!",
    "Aik aadmi doctor ke paas gaya aur bola: Doctor sahab, jab main chai peeta hoon to meri daayi aankh mein dard hota hai! Doctor: Pehle cup mein se chamach nikal kar piya karein!",
    "Customer: Bhai, is computer mein kya khas baat hai? Shopkeeper: Sir, ye itna fast hai ke mouse click karne se pehle hi hang ho jata hai!",
    "Pappu ne dost se poocha: Yaar agar bijli chali jaye to tum kya karte ho? Dost: Main mobile ki torch chala kar generator dhoondta hoon!",
    "Aik shakhs ne Google se poocha: Meri biwi kahan hai? Google ne jawab diya: Search band karein aur chup chaap bartan dho lein!",
]

SHORT_STORIES: list[str] = [
    "Aik dafa ka zikr hai, aik choti si chiriya thi jo roz mehnat se dana jama karti thi. Aik din bara toofan aaya, sab parinday ghabra gaye, magar us chiriya ke paas uski mehnat ka phal tha aur uska ghosla mehfooz raha. Sabaq: Mehnat aur sabar hamesha kamyabi dilate hain!",
    "Aik dafa ka zikr hai, do mukhlis dost jungle se guzar rahe the. Raastay mein mushkilaat aayin magar unhon ne aik doosray ka sath kabhi nahi chora. Unhon ne seekha ke sachay dost har toofan mein dhaal ban kar kharay rehtay hain!",
    "Aik badshah ne aik aqalmand wazeer se poocha: Dunya ki sab se bari taqat kya hai? Wazeer ne muskura kar kaha: Sabar aur meethi zabaan! Jis ke paas ye do cheezein hon, wo dunya ke har dil ko jeet sakta hai.",
]


class CommandResult(BaseModel):

    """Result of router matching and command dispatch."""
    matched: bool
    success: bool = False
    message: str = ""
    tool_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CommandRouter:
    """Layer 1 pattern and regex intent router."""

    def __init__(
        self,
        confirmation_manager: ConfirmationManager | None = None,
        action_logger: ActionLogger | None = None,
        ollama_client: OllamaClient | None = None,
        groq_client: GroqClient | None = None,
        enable_llm_fallback: bool = True,
    ) -> None:
        """Initialize CommandRouter.

        Args:
            confirmation_manager: Manager for confirming dangerous actions (Rule 5).
            action_logger: Action audit logger (Rule 12).
            ollama_client: Optional Ollama client for Layer 2 fallback.
            groq_client: Optional Groq client for super-fast cloud reasoning.
            enable_llm_fallback: Whether to instantiate LLM clients if not provided.
        """
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.action_logger = action_logger or ActionLogger()
        self.groq_client = groq_client or GroqClient()

        if ollama_client is not None:
            self.ollama_client = ollama_client
        elif enable_llm_fallback:
            try:
                from core.config import load_config
                cfg = load_config()
                self.ollama_client = OllamaClient(
                    base_url=cfg.brain.ollama_endpoint,
                    model=cfg.brain.model_name,
                    keep_alive=cfg.brain.keep_alive,
                    timeout_sec=cfg.brain.timeout_seconds,
                    confirmation_manager=self.confirmation_manager,
                    action_logger=self.action_logger,
                )
            except Exception:
                self.ollama_client = OllamaClient(
                    confirmation_manager=self.confirmation_manager,
                    action_logger=self.action_logger,
                )
        else:
            self.ollama_client = None



    def sanitize_input(self, raw_text: str) -> str:
        """Sanitize raw transcribed speech or user input.

        Args:
            raw_text: Untrusted speech string.

        Returns:
            Sanitized, lowercased string truncated to safe length.
        """
        if not raw_text or not isinstance(raw_text, str):
            return ""

        # Limit length to prevent regex DoS
        truncated = raw_text[:MAX_INPUT_LENGTH]

        # Strip null bytes and control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', truncated)

        # Normalize whitespace and lowercase
        normalized = " ".join(cleaned.strip().split()).lower()

        # Strip leading/trailing punctuation added by speech recognition
        normalized = re.sub(r'^[^\w]+|[.?!,:;\'"]+$', '', normalized).strip()
        return normalized

    def _match_candidate(self, text: str) -> tuple[str, dict[str, Any]] | None:
        """Match command text against Layer 1 regex rules."""
        if not text:
            return None

        # 0. Immediate Stop / Silence commands
        if re.search(
            r'^(?:please\s+|ok\s+|okay\s+|okey\s+|theek\s+hai\s+|hey\s+age\s+|age\s+|suno\s+)?(?:stop|stop\s+it|stop\s+talking|stop\s+speaking|quiet|silence|shut\s+up|halt|ruko|ruk\s+jao|chup|chup\s+karo|chup\s+ho\s+jao|bas|bas\s+karo)$',
            text,
        ) or text in ("stop", "ok stop", "okey stop", "okay stop", "ruko", "ruk jao", "chup", "chup karo", "bas karo"):
            return "stop", {}

        # 1. Close all windows (English & Roman Urdu)
        if re.search(
            r'^(?:close|quit|exit|shut|terminate)\s+all(?:\s+windows|\s+apps|\s+applications)?$',
            text,
        ) or re.search(
            r'^(?:sab|sari|tamam)\s+(?:windows|apps|applications|kuch)?\s*(?:band\s+karo|band\s+kardo|close\s+karo|close\s+kardo)$',
            text,
        ) or text in ("close all", "sab band karo", "sab band kardo", "everything close karo"):
            return "close_all", {}

        # 2. Open web destinations directly in browser
        if re.search(r'^(?:open|launch|go\s+to|start)\s+youtube$', text) or re.search(r'^youtube\s*(?:kholo|khol\s+do|chalao|on\s+karo|open\s+karo)?$', text):
            return "web_search", {"query": "youtube"}

        if re.search(r'^(?:open|launch|go\s+to|start)\s+google$', text) or re.search(r'^google\s*(?:kholo|khol\s+do|on\s+karo|open\s+karo)?$', text):
            return "web_search", {"query": "google"}

        # 3. YouTube Search / Play (Songs, Naats, Videos)
        m_yt = re.search(
            r'^(?:search\s+youtube\s+for|find\s+on\s+youtube|play\s+on\s+youtube|youtube\s+search\s+for|watch\s+on\s+youtube)\s+(.+)$',
            text,
        )
        if m_yt:
            return "youtube_search", {"query": m_yt.group(1).strip()}

        m_yt_play = re.search(r'^(?:play|find|watch)\s+(.+)\s+(?:on|in)\s+youtube$', text)
        if m_yt_play:
            return "youtube_search", {"query": m_yt_play.group(1).strip()}

        m_yt_ur = re.search(
            r'^(?:youtube\s+(?:par|pe|mein)\s+)?(.+?)\s+(?:youtube\s+(?:par|pe)\s+)?(?:chalao|chala\s+do|lagao|laga\s+do|search\s+karo|play\s+karo)$',
            text,
        )
        if m_yt_ur:
            raw_q = m_yt_ur.group(1).strip()
            is_media = "youtube" in text or any(k in text for k in ("gana", "song", "naat", "tilawat", "video", "qawwali", "music"))
            if is_media and raw_q and not re.search(r'[;&|><]', raw_q):
                return "youtube_search", {"query": raw_q}

        m_yt_ur_pre = re.search(
            r'^(?:youtube\s+(?:par|pe)\s+search\s+karo|search\s+karo\s+youtube\s+pe|search\s+karo\s+youtube\s+par)\s+(.+)$',
            text,
        )
        if m_yt_ur_pre:
            return "youtube_search", {"query": m_yt_ur_pre.group(1).strip()}

        # 4. Web Search
        m_web = re.search(
            r'^(?:search\s+(?:the\s+)?(?:web|google|internet)\s+for|search\s+for|google\s+for|google|look\s+up)\s+(.+)$',
            text,
        )
        if m_web:
            return "web_search", {"query": m_web.group(1).strip()}

        m_web_ur = re.search(
            r'^(?:google\s+(?:par|pe)\s+search\s+karo|net\s+par\s+search\s+karo|search\s+karo)\s+(.+)$',
            text,
        )
        if m_web_ur:
            return "web_search", {"query": m_web_ur.group(1).strip()}

        # 5. Open Photos / Images / Gallery (English & Roman Urdu)
        m_photo_en = re.search(
            r'^(?:open|show|view)\s+(?:the\s+|my\s+)?(?:photo|picture|pic|image|gallery)\s*(.+)?$',
            text,
        )
        if m_photo_en:
            q = (m_photo_en.group(1) or "").strip()
            return "open_app", {"app_name": f"photo {q}" if q else "pictures"}

        m_photo_ur = re.search(
            r'^(?:photo|picture|pic|image|tasveer)\s+(?:kholo|khol\s+do|dikhao|dikhayein|open\s+karo)\s*(.+)?$',
            text,
        )
        if m_photo_ur:
            q = (m_photo_ur.group(1) or "").strip()
            return "open_app", {"app_name": f"photo {q}" if q else "pictures"}

        m_photo_ur_pre = re.search(
            r'^(?:dikhao|dikhayein)\s+(?:the\s+|meri\s+)?(?:photo|picture|pic|image|tasveer)\s*(.+)?$',
            text,
        )
        if m_photo_ur_pre:
            q = (m_photo_ur_pre.group(1) or "").strip()
            return "open_app", {"app_name": f"photo {q}" if q else "pictures"}

        # 6. Open Local Videos (English & Roman Urdu)
        m_video_en = re.search(
            r'^(?:open|play|show|view)\s+(?:the\s+|my\s+)?(?:video|videos)\s*(.+)?$',
            text,
        )
        if m_video_en and "youtube" not in text:
            q = (m_video_en.group(1) or "").strip()
            return "open_app", {"app_name": f"video {q}" if q else "videos"}

        m_video_ur = re.search(
            r'^(?:video|videos)\s+(?:kholo|khol\s+do|chalao|chala\s+do|play\s+karo|open\s+karo)\s*(.+)?$',
            text,
        )
        if m_video_ur and "youtube" not in text:
            q = (m_video_ur.group(1) or "").strip()
            return "open_app", {"app_name": f"video {q}" if q else "videos"}

        # 7. Open file or folder specifically
        m_file = re.search(
            r'^(?:open|launch|view|read|show)\s+(?:the\s+|my\s+)?(?:file|document|folder|directory)\s+([a-z0-9_\-\s.]+)$',
            text,
        )
        if m_file:
            target = m_file.group(1).strip()
            if not re.search(r'[;&|><]', target):
                resolved_target = APP_ALIASES.get(target, target)
                return "open_app", {"app_name": resolved_target}

        # 8. Find and play any media on computer (e.g. "explorer and find out if any song or videos are there so please play it")
        if ("song" in text or "video" in text or "gana" in text) and any(w in text for w in ("find", "play it", "play any", "chalao", "play a video", "play a song", "koi")) and "youtube" not in text:
            return "open_app", {"app_name": "play_any_media"}

        # 9. Open App, Folder, or File (English & Roman Urdu)
        compound_words = {"and", "then", "if", "so", "please", "find", "check", "there", "aur", "agar", "to", "bhi"}

        m_open_en = re.search(
            r'^(?:open|launch|start|run|bring\s+up|show)\s+(?:the\s+|my\s+)?([a-z0-9_\-\s.]+)$',
            text,
        )
        if m_open_en:
            app_raw = m_open_en.group(1).strip()
            words = app_raw.split()
            if len(words) <= 4 and not any(w in compound_words for w in words):
                app_clean = re.sub(r'\s+(?:folder|app|application|software|browser)$', '', app_raw).strip()
                if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                    resolved_app = APP_ALIASES.get(app_clean, app_clean)
                    return "open_app", {"app_name": resolved_app}

        m_open_ur_post = re.search(
            r'^([a-z0-9_\-\s.]+?)\s+(?:kholo|khol\s+do|khol\s+dein|chalao|chala\s+do|dikhao|dikhayein|open\s+karo|open\s+kardo|open\s+karein|start\s+karo|on\s+karo|on\s+kardo)$',
            text,
        )
        if m_open_ur_post:
            app_raw = m_open_ur_post.group(1).strip()
            words = app_raw.split()
            if len(words) <= 4 and not any(w in compound_words for w in words):
                app_clean = re.sub(r'^(?:mera|meri|the)\s+', '', app_raw).strip()
                app_clean = re.sub(r'\s+(?:folder|app|application|software|browser)$', '', app_clean).strip()
                if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                    resolved_app = APP_ALIASES.get(app_clean, app_clean)
                    return "open_app", {"app_name": resolved_app}

        m_open_ur_pre = re.search(
            r'^(?:kholo|khol\s+do|khol\s+dein|chalao|chala\s+do|dikhao|dikhayein|start\s+karo|on\s+karo)\s+(?:the\s+|mera\s+|meri\s+)?([a-z0-9_\-\s.]+)$',
            text,
        )
        if m_open_ur_pre:
            app_raw = m_open_ur_pre.group(1).strip()
            words = app_raw.split()
            if len(words) <= 4 and not any(w in compound_words for w in words):
                app_clean = re.sub(r'\s+(?:folder|app|application|software|browser)$', '', app_raw).strip()
                if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                    resolved_app = APP_ALIASES.get(app_clean, app_clean)
                    return "open_app", {"app_name": resolved_app}

        # 7. Close App (English & Roman Urdu)
        m_close_en = re.search(
            r'^(?:close|quit|exit|terminate|kill|shut)\s+(?:the\s+)?([a-z0-9_\-\s]+)$',
            text,
        )
        if m_close_en:
            app_raw = m_close_en.group(1).strip()
            app_clean = re.sub(r'\s+(?:app|application|window)$', '', app_raw).strip()
            if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                resolved_app = APP_ALIASES.get(app_clean, app_clean)
                return "close_app", {"app_name": resolved_app}

        m_close_ur_post = re.search(
            r'^([a-z0-9_\-\s]+?)\s+(?:band\s+karo|band\s+kardo|band\s+karein|close\s+karo|close\s+kardo|close\s+karein|hatao|hata\s+do|off\s+karo)$',
            text,
        )
        if m_close_ur_post:
            app_raw = m_close_ur_post.group(1).strip()
            app_clean = re.sub(r'\s+(?:app|application|window)$', '', app_raw).strip()
            if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                resolved_app = APP_ALIASES.get(app_clean, app_clean)
                return "close_app", {"app_name": resolved_app}

        m_close_ur_pre = re.search(
            r'^(?:band\s+karo|band\s+kardo|close\s+karo|hata\s+do|off\s+karo)\s+([a-z0-9_\-\s]+)$',
            text,
        )
        if m_close_ur_pre:
            app_raw = m_close_ur_pre.group(1).strip()
            app_clean = re.sub(r'\s+(?:app|application|window)$', '', app_raw).strip()
            if not re.search(r'[;&|><]', app_clean) and app_clean not in PRONOUNS_AND_VAGUE:
                resolved_app = APP_ALIASES.get(app_clean, app_clean)
                return "close_app", {"app_name": resolved_app}


        # 8. Volume Controls
        if re.search(r'^(?:turn\s+)?volume\s+up$', text) or re.search(r'^(?:increase|raise|boost)\s+volume$', text) or text in ("louder", "sound up", "make it louder", "awaz barhao", "awaz barha do", "awaz tez karo", "awaz ziada karo", "volume barhao", "volume barha do", "volume tez karo", "sound barhao"):
            return "set_volume", {"delta": 10}

        if re.search(r'^(?:turn\s+)?volume\s+down$', text) or re.search(r'^(?:decrease|lower|reduce)\s+volume$', text) or text in ("quieter", "sound down", "make it softer", "awaz kam karo", "awaz kam kardo", "awaz ahista karo", "awaz dheemi karo", "volume kam karo", "volume kam kardo", "sound kam karo"):
            return "set_volume", {"delta": -10}

        m_vol_level = re.search(r'^(?:set\s+)?(?:volume|sound|awaz)\s+(?:to\s+)?(\d{1,3})(?:%|\s*percent)?(?:\s*karo|\s*kardo)?$', text)
        if m_vol_level:
            level = int(m_vol_level.group(1))
            if 0 <= level <= 100:
                return "set_volume", {"level": level}

        if text in ("mute", "mute volume", "mute audio", "mute sound", "silent", "silent karo", "awaz band karo", "awaz band kardo"):
            return "set_volume", {"mute": True}
        if text in ("unmute", "unmute volume", "unmute audio", "unmute sound", "awaz kholo", "awaz on karo"):
            return "set_volume", {"mute": False}

        # 9. Brightness Controls
        if re.search(r'^(?:turn\s+)?brightness\s+up$', text) or re.search(r'^(?:increase|raise)\s+brightness$', text) or text in ("brighter", "make screen brighter", "brightness barhao", "brightness tez karo", "roshni barhao", "roshni tez karo", "screen bright karo"):
            return "set_brightness", {"delta": 10}

        if re.search(r'^(?:turn\s+)?brightness\s+down$', text) or re.search(r'^(?:decrease|lower|dim)\s+brightness$', text) or text in ("dimmer", "dim screen", "make screen darker", "brightness kam karo", "brightness kam kardo", "roshni kam karo", "roshni kam kardo", "screen dim karo"):
            return "set_brightness", {"delta": -10}

        m_bright_level = re.search(r'^(?:set\s+)?(?:brightness|roshni)\s+(?:to\s+)?(\d{1,3})(?:%|\s*percent)?(?:\s*karo|\s*kardo)?$', text)
        if m_bright_level:
            level = int(m_bright_level.group(1))
            if 0 <= level <= 100:
                return "set_brightness", {"level": level}

        # 10. Lock Screen
        if re.search(r'^(?:lock|lock\s+the|lock\s+my)\s+(?:screen|pc|computer|workstation|desktop|laptop)$', text) or re.search(r'^(?:screen|pc|computer|laptop)\s*(?:lock\s+karo|lock\s+kardo|lock)$', text) or text in ("lock", "lock karo", "lock kardo"):
            return "lock_screen", {}

        # 11. Type Text
        m_type = re.search(r'^(?:type|type\s+text|enter\s+text|write)\s+(.+)$', text)
        if m_type:
            return "type_text", {"text": m_type.group(1)}

        m_type_ur = re.search(r'^(?:type\s+karo|likho|text\s+likho)\s+(.+)$', text)
        if m_type_ur:
            return "type_text", {"text": m_type_ur.group(1)}

        # 12. System Shutdown (Dangerous)
        if re.search(r'^(?:shut\s*down|turn\s*off)\s+(?:the\s+)?(?:pc|computer|system|laptop)$', text) or re.search(r'^(?:computer|pc|laptop|system)\s*(?:band\s+karo|shut\s*down\s*karo)$', text) or text in ("shutdown", "shut down", "pc band karo"):
            return "shutdown", {}

        # 13. System Restart (Dangerous)
        if re.search(r'^(?:restart|reboot)\s+(?:the\s+)?(?:pc|computer|system|laptop)$', text) or re.search(r'^(?:computer|pc|laptop|system)\s*(?:restart\s*karo|reboot\s*karo)$', text) or text in ("restart", "reboot", "restart karo"):
            return "restart", {}

        # 14. Desktop Layout Management (Save safe, Restore dangerous)
        if re.search(r'^(?:save|backup)\s+(?:my\s+)?(?:desktop|layout)$', text) or text in ("layout save karo", "desktop save karo"):
            return "save_layout", {}

        if re.search(r'^(?:restore|load)\s+(?:my\s+)?(?:desktop|layout)$', text) or text in ("layout restore karo", "desktop restore karo"):
            return "restore_layout", {}

        return None

    def route_intent(self, text: str) -> tuple[str, dict[str, Any]] | None:
        """Classify input text into (tool_name, tool_params).

        Args:
            text: Sanitized input command.

        Returns:
            Tuple of (tool_name, params) or None if no rule matches.
        """
        if not text:
            return None

        # Clean punctuation and normalize whitespace
        norm_text = re.sub(r'^[^\w]+|[.?!,:;\'"]+$', '', text.strip().lower())
        norm_text = " ".join(norm_text.split())

        # Strip optional wake words and polite prefixes if followed by a command
        clean_cmd = re.sub(
            r'^(?:hey\s+age|my\s+age|ok\s+age|age|hi\s+age|suno\s+age|suno|bhai|yaar|please|meharbani\s+karke|can\s+you|could\s+you|zara)[,\s]+',
            '',
            norm_text,
        ).strip()
        clean_cmd = re.sub(
            r'[,\s]+(?:please|thank\s+you|thanks|yaar|bhai|zara)$',
            '',
            clean_cmd,
        ).strip()

        candidates = [clean_cmd] if clean_cmd and clean_cmd != norm_text else []
        candidates.append(norm_text)

        for candidate in candidates:
            match = self._match_candidate(candidate)
            if match:
                return match

        return None

    def _check_conversational(self, text: str) -> CommandResult | None:
        """Handle offline conversational queries, jokes, stories, feelings, time, and help."""
        from datetime import datetime

        norm = re.sub(r'^[^\w]+|[.?!,:;\'"]+$', '', text.strip().lower())
        norm = " ".join(norm.split())

        # 0. Ambiguous open / close commands (ask for clarification instead of crashing)
        if re.search(r'^(?:open\s+(?:it|this|that|app|something|anything|file|folder)|kholo\s+(?:isay|isko|usko|ye|yeh)|(?:isay|isko|usko|ye|yeh)\s+kholo)$', norm) or norm in ("open it", "open this", "open that", "kholo isay", "isay kholo", "isko kholo"):
            return CommandResult(
                matched=True,
                success=True,
                message="Aap konsi application ya folder open karna chahte hain? Jaise Chrome, Word, Excel, ya VS Code.",
                tool_name="conversation",
            )
        if re.search(r'^(?:close\s+(?:it|this|that|app|something|anything)|band\s+karo\s+(?:isay|isko|usko|ye|yeh)|(?:isay|isko|usko|ye|yeh)\s+band\s+karo)$', norm) or norm in ("close it", "close this", "close that", "band karo isay", "isay band karo", "isko band karo"):
            return CommandResult(
                matched=True,
                success=True,
                message="Aap konsi application band karna chahte hain? Jaise Chrome, Word, ya Notepad.",
                tool_name="conversation",
            )

        # 1. Jokes & Latifay
        if re.search(
            r'^(?:tell\s+me\s+a\s+joke|tell\s+me\s+joke|joke|tell\s+a\s+joke|koi\s+joke\s+sunao|ek\s+joke\s+sunao|joke\s+sunao|joke\s+batao|chutkula\s+sunao|latafa\s+sunao|latifa\s+sunao|make\s+me\s+laugh|hanso)$',
            norm,
        ):
            joke = random.choice(ROBOT_JOKES)
            return CommandResult(
                matched=True,
                success=True,
                message=joke,
                tool_name="conversation",
            )

        # 2. Stories & Kahanian
        if re.search(
            r'^(?:tell\s+me\s+a\s+story|tell\s+a\s+story|story|kahani\s+sunao|ek\s+kahani\s+sunao|aik\s+kahani\s+sunao|koi\s+kahani\s+sunao|story\s+sunao|koi\s+story\s+sunao)$',
            norm,
        ):
            story = random.choice(SHORT_STORIES)
            return CommandResult(
                matched=True,
                success=True,
                message=story,
                tool_name="conversation",
            )

        # 3. User Age & Name queries
        if re.search(
            r'^(?:what\s+is\s+my\s+age|meri\s+age\s+kya\s+hai|meri\s+umar\s+kya\s+hai|meri\s+umar\s+kitni\s+hai|my\s+age\s+kya\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Aap meri dost aur owner hain! Agar aap chahein to mujhe apni age aur details bata sakti hain.",
                tool_name="conversation",
            )

        if re.search(
            r'^(?:what\s+is\s+my\s+name|mera\s+naam\s+kya\s+hai|mera\s+naam|who\s+am\s+i|main\s+kon\s+hoon)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Aap meri boss aur dost hain! Main aapka loyal desktop assistant hoon.",
                tool_name="conversation",
            )

        # 4. Assistant Age & Identity queries
        if re.search(
            r'^(?:what\s+is\s+your\s+age|how\s+old\s+are\s+you|tumhari\s+age\s+kya\s+hai|tumhari\s+umar\s+kya\s+hai|tum\s+kitne\s+saal\s+ke\s+ho)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main ek AI desktop assistant hoon, meri koi physical age nahi hai! Main hamesha aapki madad ke liye hazir hoon.",
                tool_name="conversation",
            )

        if re.search(
            r'^(?:who\s+are\s+you|what\s+is\s+your\s+name|tum\s+kon\s+ho|aap\s+kon\s+hain|apna\s+naam\s+batao|tumhara\s+naam\s+kya\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main AGE hoon, aapka personal offline AI desktop assistant. Main aapke computer ki har application open aur close kar sakta hoon.",
                tool_name="system_info",
            )

        # 5. Greetings & wake acknowledgements
        if re.search(
            r'^(?:hey\s+age|my\s+age|hi\s+age|hello\s+age|hello|hi|hey|salam|assalam\s*o\s*alaikum|assalam\s*alaikum|aoa|adaab|are\s+you\s+there)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Walaikum Assalam! Hello, I am AGE, your personal AI assistant. How can I help you?",
                tool_name="conversation",
            )

        # 6. How are you & feelings
        if re.search(
            r'^(?:how\s+are\s+you|how\s+are\s+you\s+doing|how\s+is\s+it\s+going|what\'?s\s+up|kya\s+haal\s+hai|kese\s+ho|kaise\s+ho|sab\s+theek\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main bilkul theek hoon! I am doing great. How can I help you with your computer today?",
                tool_name="conversation",
            )

        # 7. Tiredness / Sleepiness empathy
        if re.search(
            r'^(?:thakan\s+ho\s+rahi\s+hai|thak\s+gayi\s+hoon|thak\s+gaya\s+hoon|bohat\s+thak\s+gayi\s+hoon|i\s+am\s+tired|tired|neend\s+aa\s+rahi\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Aap thori der aaram kar lein! Agar aap chahein to main YouTube par koi sukoon bakhsh music ya tilawat chala sakta hoon.",
                tool_name="conversation",
            )

        # 8. Boredom / Fun
        if re.search(
            r'^(?:bor\s+ho\s+rahi\s+hoon|bor\s+ho\s+raha\s+hoon|bored|i\s+am\s+bored|maza\s+nahi\s+aa\s+raha|kuch\s+maza\s+nahi\s+aa\s+raha)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main aapka mood fresh karne ke liye koi mazedar joke suna sakta hoon, ya YouTube par koi comedy video ya gana chala sakta hoon!",
                tool_name="conversation",
            )

        # 9. Friendly conversation request
        if re.search(
            r'^(?:baat\s+karo|mujhse\s+baat\s+karo|talk\s+to\s+me|kuch\s+bolo|kuch\s+sunao|gup\s+shup\s+lagao)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Ji zaroor! Main hamesha aapke sath hoon. Aap batayein, aaj ka din kaisa guzra aur aap kya karna chahti hain?",
                tool_name="conversation",
            )

        # 10. Status / What are you doing
        if re.search(
            r'^(?:what\s+are\s+you\s+doing|kya\s+kar\s+rahe\s+ho|kya\s+kar\s+rahi\s+ho|kya\s+chal\s+raha\s+hai|kya\s+ho\s+raha\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main bilkul ready hoon aapki commands sunne ke liye! Aap jo bhi hukam dein, main foran poora karoon ga.",
                tool_name="conversation",
            )

        # 11. Praise & Compliments
        if re.search(
            r'^(?:you\s+are\s+good|you\s+are\s+great|tum\s+bohat\s+ache\s+ho|tum\s+ache\s+ho|shabash|good\s+job|nice\s+work|awesome|well\s+done)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Bohat bohat shukriya! Aapki madad karna mere liye sab se bari khushi hai.",
                tool_name="conversation",
            )

        # 12. Polite greetings (morning/evening)
        if re.search(r'^(?:good\s+morning|good\s+afternoon|good\s+evening)$', norm):
            return CommandResult(
                matched=True,
                success=True,
                message="Hello! Have a wonderful day. How can I assist you?",
                tool_name="conversation",
            )

        # 13. Gratitude
        if re.search(
            r'^(?:thank\s+you|thanks|thank\s+you\s+so\s+much|shukriya|bohat\s+shukriya|shabash|bohat\s+ache|theek\s+hai)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Aapka bohat shukriya! You're welcome. Let me know if you need anything else.",
                tool_name="conversation",
            )

        # 14. Farewells
        if re.search(
            r'^(?:goodbye|bye|see\s+you|see\s+you\s+later|allah\s*hafiz|khuda\s*hafiz|alvida)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Allah Hafiz! Goodbye, have a great time.",
                tool_name="conversation",
            )

        # 15. Time query
        if re.search(
            r'^(?:what\s+is\s+the\s+time|what\s+time\s+is\s+it|tell\s+me\s+the\s+time|current\s+time|time|time\s+kya\s+hua\s+hai|kitne\s+baj\s+rahe\s+hain|waqt\s+kya\s+hai|time\s+batao)$',
            norm,
        ):
            time_str = datetime.now().astimezone().strftime("%I:%M %p").lstrip("0")
            return CommandResult(
                matched=True,
                success=True,
                message=f"The current time is {time_str}. (Waqt: {time_str})",
                tool_name="system_info",
                data={"time": time_str},
            )

        # 16. Date query
        if re.search(
            r'^(?:what\s+is\s+the\s+date|what\s+is\s+today\'?s?\s+date|tell\s+me\s+the\s+date|today\'?s?\s+date|date|aaj\s+kya\s+date\s+hai|aaj\s+konsa\s+din\s+hai|aaj\s+ki\s+date\s+kya\s+hai|date\s+batao)$',
            norm,
        ):
            date_str = datetime.now().astimezone().strftime("%A, %B %d, %Y")
            return CommandResult(
                matched=True,
                success=True,
                message=f"Today is {date_str}.",
                tool_name="system_info",
                data={"date": date_str},
            )

        # 17. Capabilities / Help query
        if re.search(
            r'^(?:what\s+can\s+you\s+do|help|what\s+are\s+your\s+commands|tum\s+kya\s+kar\s+sakte\s+ho|aap\s+kya\s+kar\s+sakte\s+hain|kya\s+kya\s+kar\s+sakte\s+ho|madad)$',
            norm,
        ):
            return CommandResult(
                matched=True,
                success=True,
                message="Main aapke laptop par Chrome, Word, Excel, PowerPoint, folders aur files open/close kar sakta hoon, YouTube par videos chala sakta hoon, volume aur brightness control kar sakta hoon, screen lock kar sakta hoon, aur aapse baat cheet kar sakta hoon.",
                tool_name="system_info",
            )

        return None



    def execute_command(
        self,
        raw_input: str,
        voice_pipeline: Any | None = None,
        force_confirmed: bool = False,
    ) -> CommandResult:
        """Route and execute command with security checks and confirmations.

        Args:
            raw_input: Raw spoken or typed command.
            voice_pipeline: Optional VoicePipeline for spoken confirmations.
            force_confirmed: Internal testing override flag for simulation.

        Returns:
            CommandResult.
        """
        clean_text = self.sanitize_input(raw_input)
        if not clean_text:
            return CommandResult(matched=False, message="Input is empty.")

        intent = self.route_intent(clean_text)
        if intent and intent[0] == "stop":
            if voice_pipeline and hasattr(voice_pipeline, "stop"):
                voice_pipeline.stop()
            self.action_logger.log("stop", {}, "Stopped.", success=True)
            return CommandResult(
                matched=True,
                success=True,
                message="Stopped.",
                tool_name="stop",
            )

        if not intent:
            conv_res = self._check_conversational(clean_text)

            # If Groq is configured, route open questions and chat to Groq with multi-turn memory
            if self.groq_client and self.groq_client.is_configured:
                is_quick_clock = conv_res and conv_res.tool_name == "system_info" and (conv_res.data.get("time") or conv_res.data.get("date"))
                if not is_quick_clock:
                    try:
                        logger.info("Routing query to Groq Cloud with multi-turn memory...")
                        reply = self.groq_client.chat(clean_text)
                        self.action_logger.log("groq_chat", {"prompt": clean_text}, reply, success=True)

                        # Check and execute any action tag from Groq
                        m_act = re.search(r'\[ACTION:\s*([a-z_]+)(?:\s+(.*?))?\]', reply, re.IGNORECASE)
                        clean_reply = reply
                        act_data: dict[str, Any] = {"provider": "groq", "model": self.groq_client.model}

                        if m_act:
                            act_tool_name = m_act.group(1).lower()
                            act_arg = (m_act.group(2) or "").strip()
                            clean_reply = re.sub(r'\[ACTION:.*?\]', '', reply).strip()
                            tool_inst = registry.get(act_tool_name)
                            if tool_inst:
                                logger.info("Executing Groq action tag tool '%s' with argument: '%s'", act_tool_name, act_arg)
                                if act_tool_name == "open_app":
                                    tool_res = tool_inst.run(app_name=act_arg or "play_any_media")
                                elif act_tool_name == "youtube_search":
                                    tool_res = tool_inst.run(query=act_arg)
                                elif act_tool_name == "web_search":
                                    tool_res = tool_inst.run(query=act_arg)
                                elif act_tool_name == "set_volume":
                                    try:
                                        tool_res = tool_inst.run(level=int(act_arg))
                                    except ValueError:
                                        tool_res = None
                                else:
                                    tool_res = None
                                if tool_res and tool_res.data:
                                    act_data.update(tool_res.data)

                        return CommandResult(
                            matched=True,
                            success=True,
                            message=clean_reply,
                            tool_name="groq_chat",
                            data=act_data,
                        )
                    except Exception as e:
                        logger.warning("Groq Cloud chat error: %s. Falling back to local handlers.", e)

            if conv_res:
                self.action_logger.log(
                    conv_res.tool_name or "conversation",
                    {},
                    conv_res.message,
                    success=True,
                )
                return conv_res

            logger.info("No Layer 1 rule matched for input: '%s'", clean_text)

            # If user configured Groq as primary provider and key is present, don't fall back to offline Ollama
            if self.groq_client and self.groq_client.is_configured:
                return CommandResult(
                    matched=False,
                    success=False,
                    message="Groq Cloud se rabta nahi ho saka. Barah-e-karam apna internet check karein.",
                )

            if self.ollama_client:
                logger.info("Falling back to Layer 2 Ollama LLM...")
                llm_res = self.ollama_client.chat(
                    prompt=clean_text,
                    voice_pipeline=voice_pipeline,
                    force_confirmed=force_confirmed,
                )
                if not llm_res.success and llm_res.message == OFFLINE_MESSAGE:
                    return CommandResult(
                        matched=False,
                        success=False,
                        message=OFFLINE_MESSAGE,
                    )

                return CommandResult(
                    matched=True,
                    success=llm_res.success,
                    message=llm_res.message,
                    tool_name=llm_res.data.get("tool_name"),
                    data=llm_res.data,
                )

            return CommandResult(
                matched=False,
                message=f"I didn't recognize the command: '{clean_text}'.",
            )

        tool_name, params = intent
        tool = registry.get(tool_name)
        if not tool:
            return CommandResult(
                matched=True,
                success=False,
                message=f"Tool '{tool_name}' is not registered.",
                tool_name=tool_name,
            )

        # Security Rule 5: Dangerous actions ALWAYS require confirmation
        if tool.is_dangerous:
            confirmed = force_confirmed or self.confirmation_manager.request_confirmation(
                action_name=tool_name,
                prompt=f"Are you sure you want to {tool_name}? Please say yes or no.",
                voice_pipeline=voice_pipeline,
            )
            if not confirmed:
                msg = f"Action '{tool_name}' was cancelled."
                self.action_logger.log(tool_name, params, msg, success=False)
                return CommandResult(
                    matched=True,
                    success=False,
                    message=msg,
                    tool_name=tool_name,
                )

        # Execute tool via strict Pydantic validation
        result = tool.run(**params)

        # Security Rule 12: Audit action execution
        self.action_logger.log(tool_name, params, result.message, success=result.success)

        return CommandResult(
            matched=True,
            success=result.success,
            message=result.message,
            tool_name=tool_name,
            data=result.data,
        )
