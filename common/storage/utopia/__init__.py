"""
Utopia storage module for vcon-server

Pushes each vCon into a Utopia knowledge base (https://github.com/deeplethe/utopia),
a bitemporal knowledge graph that extracts dated facts from documents.

Utopia reads prose, not JSON, and dates a document only from a leading
``YYYY-MM-DD`` line in a Markdown file. So the vCon is rendered here as dated
sentences and uploaded as ``<uuid>.md``. The filename is the only link between
the vCon and Utopia's own document id: ``get`` is not offered, because Utopia
holds our rendering, not the vCon.

Endpoints used (all under ``base_url``):
- POST   auth/login                  - Trade the service account for a JWT
- GET    kbs/{kb_id}/documents?q=    - Find this vCon's document by filename
- POST   kbs/{kb_id}/documents       - Upload the rendering (multipart)
- DELETE documents/{id}              - Tombstone a superseded rendering

Configuration options:
- base_url: Utopia REST API root (default: http://127.0.0.1:1516/api/v1)
- kb_id: Knowledge base UUID. Required
- email, password: Utopia service account with Editor role on the KB. Required.
  Utopia's REST API takes session JWTs only, not personal access tokens
- timeout: Request timeout in seconds (default: 30)
- transient_retries: Retries for transient failures (default: 3)
- transient_backoff_base_s: Backoff factor in seconds (default: 0.5)
- require_analysis_grant: Skip vCons whose lawful basis does not grant
  ``analysis`` (default: False)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
# ponytail: shared retry policy. POST retries are safe here too: Utopia skips
# an upload whose sha256 is already in the KB.
from storage.vcon_mcp import _session
from vcon import Vcon

logger = init_logger(__name__)

default_options: Dict[str, Any] = {
    "base_url": "http://127.0.0.1:1516/api/v1",
    "kb_id": "",
    "email": "",
    "password": "",
    "timeout": 30,
    "transient_retries": 3,
    "transient_backoff_base_s": 0.5,
    "require_analysis_grant": False,
}

TRANSCRIPT_TYPES = ("transcript", "wtf_transcription")

# (base_url, email) -> JWT. ponytail: per process, re-login on 401. Utopia's
# tokens last 7 days, so this logs in about once a week per worker.
_tokens: Dict[Tuple[str, str], str] = {}


# ---------------------------------------------------------------- rendering


def _date(ts: Any) -> str:
    return str(ts)[:10] if ts else ""


def _when(ts: Any) -> str:
    """'2025-02-27 at 16:44' from an ISO 8601 instant, or just the day."""
    ts = str(ts or "")
    return f"{ts[:10]} at {ts[11:16]}" if len(ts) >= 16 else ts[:10]


def _party_label(parties: List[dict], index: Any) -> str:
    if isinstance(index, int) and 0 <= index < len(parties):
        p = parties[index] or {}
        return p.get("name") or p.get("tel") or p.get("mailto") or f"party {index}"
    return f"party {index}"


def _party_sentence(p: dict) -> str:
    who = p.get("name") or p.get("tel") or p.get("mailto") or "An unnamed party"
    sentence = f"{who} took part"
    if p.get("role"):
        sentence += f" as {p['role']}"
    reach = [f"phone {p['tel']}" if p.get("tel") and p["tel"] != who else "",
             f"email {p['mailto']}" if p.get("mailto") and p["mailto"] != who else ""]
    reach = [r for r in reach if r]
    if reach:
        sentence += ", reachable by " + " and ".join(reach)
    return sentence + "."


def _flat_ints(value: Any) -> List[int]:
    """dialog.parties may nest lists (one per channel); flatten to indexes."""
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        return [i for v in value for i in _flat_ints(v)]
    return []


def _dialog_sentence(d: dict, parties: List[dict]) -> str:
    """'On 2025-02-27 at 16:44, Ann and Bob had a recorded call lasting 240 seconds.'"""
    kind = {"recording": "a recorded call", "text": "a text conversation",
            "transfer": "a transfer", "incomplete": "an incomplete call"}.get(
        d.get("type"), "a conversation")
    names = [_party_label(parties, i) for i in _flat_ints(d.get("parties"))]
    sentence = f"{' and '.join(names)} had {kind}" if names else f"There was {kind}"
    duration = d.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        sentence += f" lasting {round(duration)} seconds"
    if d.get("start"):
        sentence = f"On {_when(d['start'])}, {sentence}"
    return sentence + "."


def _transcript_lines(body: Any) -> List[str]:
    """Tolerates wtf_transcription, OpenAI, Deepgram and legacy bodies."""
    if isinstance(body, str):
        return [body.strip()] if body.strip() else []
    if not isinstance(body, dict):
        return []
    lines = []
    for s in body.get("segments") or []:
        if isinstance(s, dict) and str(s.get("text") or "").strip():
            who = f"Speaker {s['speaker']}: " if s.get("speaker") is not None else ""
            lines.append(who + str(s["text"]).strip())
    if lines:
        return lines
    text = body.get("transcript")
    if isinstance(text, dict):
        text = text.get("text")
    text = text or body.get("text")
    return [text.strip()] if isinstance(text, str) and text.strip() else []


def _body(entry: dict) -> Any:
    try:
        body = Vcon.decoded_body(entry)
    except ValueError:  # malformed json body; render nothing rather than fail
        return None
    if isinstance(body, str) and entry.get("encoding") not in ("none", "base64url"):
        try:
            return json.loads(body)
        except ValueError:
            pass
    return body


def _purpose(att: dict) -> Optional[str]:
    return att.get("purpose") or att.get("type")


def _lawful_basis(attachments: List[dict]) -> Tuple[str, bool]:
    """One sentence for the rendering, and whether ``analysis`` is granted now.

    Never fills a gap: no attachment reads as "none recorded".
    """
    for att in attachments:
        if _purpose(att) != "lawful_basis":
            continue
        body = _body(att)
        if not isinstance(body, dict):
            continue
        granted = [g.get("purpose") for g in body.get("purpose_grants") or []
                   if isinstance(g, dict) and g.get("granted") is True and g.get("purpose")]
        expiration = body.get("expiration")
        expired = False
        if expiration:
            try:
                exp = datetime.fromisoformat(str(expiration).replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                expired = exp <= datetime.now(timezone.utc)
            except ValueError:
                expired = True  # an unreadable expiry is not a valid grant
        sentence = f"Lawful basis: {body.get('lawful_basis') or 'unspecified'}"
        sentence += f", granted for {', '.join(granted)}" if granted else ", nothing granted"
        if expiration:
            sentence += f", {'expired' if expired else 'expires'} {_date(expiration)}"
        return sentence + ".", "analysis" in granted and not expired
    return "Lawful basis: none recorded.", False


def _tags(attachments: List[dict]) -> List[str]:
    tags = []
    for att in attachments:
        if _purpose(att) != "tags":
            continue
        body = _body(att)
        if isinstance(body, dict):
            tags += [f"{k}:{v}" for k, v in body.items()]
        elif isinstance(body, list):
            tags += [str(t) for t in body]
    return tags


def render(vcon: dict) -> Tuple[str, bool]:
    """Render a vCon dict as dated Markdown sentences.

    Returns (markdown, analysis_granted).
    """
    parties = vcon.get("parties") or []
    dialogs = vcon.get("dialog") or []
    analysis = vcon.get("analysis") or []
    attachments = vcon.get("attachments") or []
    uuid = vcon.get("uuid", "unknown")

    lines: List[str] = []
    # First non-empty line is the date Utopia uses as the document's date.
    day = _date(vcon.get("created_at")) or next(
        (_date(d.get("start")) for d in dialogs if d.get("start")), "")
    if day:
        lines += [day, ""]
    lines += [f"# Conversation {uuid}", ""]
    if vcon.get("subject"):
        lines += [f"Subject: {vcon['subject']}.", ""]
    lines += [_party_sentence(p or {}) for p in parties]
    lines += [_dialog_sentence(d or {}, parties) for d in dialogs]

    for a in analysis:
        if a.get("type") == "summary":
            text = _transcript_lines(_body(a))
            if text:
                lines += ["", "Summary: " + " ".join(text)]
    for a in analysis:
        if a.get("type") in TRANSCRIPT_TYPES:
            text = _transcript_lines(_body(a))
            if not text:
                continue
            d = dialogs[a["dialog"]] if isinstance(a.get("dialog"), int) and a["dialog"] < len(dialogs) else {}
            heading = f"Transcript of the conversation on {_when(d.get('start'))}:" if d.get("start") else "Transcript:"
            lines += ["", heading, ""] + text

    tags = _tags(attachments)
    if tags:
        lines += ["", "Tagged " + ", ".join(tags) + "."]
    basis_sentence, analysis_granted = _lawful_basis(attachments)
    lines += ["", basis_sentence]
    source = f"Source: vCon {uuid}"
    if vcon.get("created_at"):
        source += f", created {vcon['created_at']}"
    for key in ("amended", "redacted"):
        ref = vcon.get(key)
        if isinstance(ref, dict) and ref.get("uuid"):
            source += f", {key} from vCon {ref['uuid']}"
    lines.append(source + ".")
    return "\n".join(lines) + "\n", analysis_granted


# --------------------------------------------------------------------- HTTP


def _opts(opts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    opts = {**default_options, **(opts or {})}
    missing = [k for k in ("kb_id", "email", "password") if not opts.get(k)]
    if missing:
        raise ValueError(f"utopia storage: missing option(s) {', '.join(missing)}")
    return opts


def _url(opts: Dict[str, Any], path: str) -> str:
    return f"{opts['base_url'].rstrip('/')}/{path.lstrip('/')}"


def _filename(vcon_uuid: str) -> str:
    return f"{vcon_uuid}.md"


def _request(session, opts: Dict[str, Any], method: str, path: str, **kwargs):
    """Authenticated request; logs in on first use and once more on a 401."""
    key = (opts["base_url"], opts["email"])
    for attempt in (0, 1):
        token = _tokens.get(key)
        if not token:
            resp = session.post(
                _url(opts, "auth/login"),
                json={"email": opts["email"], "password": opts["password"]},
                timeout=opts["timeout"],
            )
            resp.raise_for_status()
            token = _tokens[key] = resp.json()["token"]
        resp = session.request(
            method, _url(opts, path),
            headers={"Authorization": f"Bearer {token}"},
            timeout=opts["timeout"], **kwargs,
        )
        if resp.status_code != 401 or attempt:
            return resp
        _tokens.pop(key, None)


def _find(session, opts: Dict[str, Any], vcon_uuid: str) -> List[str]:
    """Ids of live Utopia documents holding this vCon's rendering."""
    resp = _request(session, opts, "GET", f"kbs/{opts['kb_id']}/documents",
                    params={"q": vcon_uuid, "limit": 200})
    resp.raise_for_status()
    name = _filename(vcon_uuid)
    return [d["id"] for d in resp.json().get("docs", []) if d.get("filename") == name]


def save(vcon_uuid: str, opts: Dict[str, Any] = None) -> None:
    """Upload the vCon's rendering; tombstone the one it supersedes.

    Upload first, delete second, so a failed upload loses nothing. Identical
    content comes back from Utopia as skipped, which is a no-op here.
    """
    opts = _opts(opts)
    vcon = VconRedis().get_vcon(vcon_uuid)
    if not vcon:
        raise ValueError(f"vCon {vcon_uuid} not found in Redis")
    text, analysis_granted = render(vcon.to_dict())
    if not analysis_granted:
        if opts["require_analysis_grant"]:
            logger.warning("utopia storage: skipped vCon %s, no lawful basis grants analysis", vcon_uuid)
            return
        logger.info("utopia storage: vCon %s has no lawful basis granting analysis", vcon_uuid)

    with _session(opts) as session:
        previous = _find(session, opts, vcon_uuid)
        resp = _request(
            session, opts, "POST", f"kbs/{opts['kb_id']}/documents",
            files={"file": (_filename(vcon_uuid), text.encode("utf-8"), "text/markdown")},
        )
        resp.raise_for_status()
        created = {d["id"] for d in resp.json().get("created") or []}
        if not created:
            logger.info("utopia storage: vCon %s unchanged in Utopia", vcon_uuid)
            return
        for doc_id in previous:
            if doc_id not in created:
                _request(session, opts, "DELETE", f"documents/{doc_id}").raise_for_status()
    logger.info("utopia storage: saved vCon %s, superseded %d", vcon_uuid, len(previous))


def delete(vcon_uuid: str, opts: Dict[str, Any] = None) -> bool:
    """Tombstone this vCon's rendering in Utopia.

    A Utopia delete is reversible: it invalidates facts with no other source
    but keeps the content. Purging (for redaction) needs KB Admin and is not
    done here.
    """
    opts = _opts(opts)
    with _session(opts) as session:
        ids = _find(session, opts, vcon_uuid)
        for doc_id in ids:
            _request(session, opts, "DELETE", f"documents/{doc_id}").raise_for_status()
    return bool(ids)
