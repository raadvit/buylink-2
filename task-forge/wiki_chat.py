import re
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def append_chat_message(wiki_path: str, role: str, sender: str, text: str) -> None:
    """Přidá zprávu do ## Chat sekce wiki souboru. No-op pokud soubor neexistuje."""
    try:
        path = Path(wiki_path)
        if not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        ts = _now_iso()
        block = f'<!-- chat-msg role="{role}" sender="{sender}" ts="{ts}" -->\n{text}\n<!-- /chat-msg -->'

        if "## Chat" in content:
            idx = content.find("## Chat")
            next_section = re.search(r'\n## ', content[idx + 7:])
            if next_section:
                insert_pos = idx + 7 + next_section.start()
                content = content[:insert_pos].rstrip() + '\n\n' + block + '\n' + content[insert_pos:]
            else:
                content = content.rstrip() + '\n\n' + block + '\n'
        else:
            metriky_match = re.search(r'\n## Metriky\b', content)
            if metriky_match:
                insert_pos = metriky_match.start()
                content = content[:insert_pos].rstrip() + '\n\n## Chat\n\n' + block + '\n' + content[insert_pos:]
            else:
                content = content.rstrip() + '\n\n## Chat\n\n' + block + '\n'

        path.write_text(content, encoding="utf-8")
    except Exception:
        pass


def read_chat_messages(wiki_path: str) -> list[dict]:
    """Parsuje ## Chat sekci wiki souboru. Vrátí [] pokud sekce chybí nebo soubor neexistuje."""
    try:
        path = Path(wiki_path)
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        pattern = re.compile(
            r'<!-- chat-msg role="([^"]*)" sender="([^"]*)" ts="([^"]*)" -->\n([\s\S]*?)\n<!-- /chat-msg -->'
        )
        return [
            {"role": m.group(1), "sender": m.group(2), "ts": m.group(3), "text": m.group(4)}
            for m in pattern.finditer(content)
        ]
    except Exception:
        return []
