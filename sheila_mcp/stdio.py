"""The Model Context Protocol over stdio, with the standard library only (James Gilmore, 2026-10-30).

Sheila's Python runtime is copied to every CSM's PC; the MCP SDK would add some twenty packages to it.
The stdio transport is newline-delimited JSON-RPC 2.0, and Sheila needs five methods of it: initialize,
tools/list, tools/call, prompts/list, prompts/get (plus ping). Like Sheila's page, which is
http.server and one HTML string, this is small enough to own.

Tools and prompts are plain functions; their JSON schemas come from their signatures. A tool call runs on
its own thread, so a slow one (a CSM's whole month, read off the share) never holds up another.
"""
import inspect
import json
import sys
import threading
import traceback
import typing

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object", list: "array"}


def _schema(fn):
    props, required = {}, []
    hints = typing.get_type_hints(fn)
    for name, p in inspect.signature(fn).parameters.items():
        t = hints.get(name, str)
        args = [a for a in typing.get_args(t) if a is not type(None)]
        t = args[0] if args else t
        t = typing.get_origin(t) or t
        props[name] = {"type": _JSON_TYPES.get(t, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(name)
        elif p.default is not None:
            props[name]["default"] = p.default
    out = {"type": "object", "properties": props}
    if required:
        out["required"] = required
    return out


class Server:
    def __init__(self, name, version, instructions=""):
        self.name, self.version, self.instructions = name, version, instructions
        self.tools, self.prompts = {}, {}
        self._out = sys.stdout
        self._write = threading.Lock()

    # ------------------------------------------------------------------ registration
    def tool(self, fn):
        self.tools[fn.__name__] = fn
        return fn

    def prompt(self, name, description):
        def deco(fn):
            self.prompts[name] = (fn, description)
            return fn
        return deco

    # ------------------------------------------------------------------ the protocol
    def tool_list(self):
        return [{"name": n, "description": inspect.cleandoc(f.__doc__ or ""), "inputSchema": _schema(f)}
                for n, f in self.tools.items()]

    def prompt_list(self):
        out = []
        for name, (fn, desc) in self.prompts.items():
            args = [{"name": a, "required": p.default is inspect.Parameter.empty}
                    for a, p in inspect.signature(fn).parameters.items()]
            out.append({"name": name, "description": desc, "arguments": args})
        return out

    def call_tool(self, name, arguments):
        fn = self.tools.get(name)
        if fn is None:
            return {"content": [{"type": "text", "text": f"No tool named {name}."}], "isError": True}
        try:
            r = fn(**(arguments or {}))
        except TypeError as e:
            return {"content": [{"type": "text", "text": f"Bad arguments for {name}: {e}"}], "isError": True}
        except (Exception, SystemExit) as e:          # noqa: BLE001 — the message goes back to Claude, verbatim
            traceback.print_exc(file=sys.stderr)
            return {"content": [{"type": "text", "text": f"{name} failed: {type(e).__name__}: {e}"}], "isError": True}
        if isinstance(r, dict) and "answer" in r:
            return {"content": [{"type": "text", "text": r["answer"]}],
                    "structuredContent": json.loads(json.dumps(r.get("data") or {}, default=str))}
        return {"content": [{"type": "text", "text": r if isinstance(r, str) else json.dumps(r, default=str)}]}

    def handle(self, msg):
        """The response to one message, or None for a notification."""
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if mid is None:                               # notifications/initialized, cancelled, ...
            return None
        if method == "initialize":
            asked = params.get("protocolVersion")
            result = {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                      "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                      "serverInfo": {"name": self.name, "version": self.version}}
            if self.instructions:
                result["instructions"] = self.instructions
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tool_list()}
        elif method == "tools/call":
            result = self.call_tool(params.get("name"), params.get("arguments"))
        elif method == "prompts/list":
            result = {"prompts": self.prompt_list()}
        elif method == "prompts/get":
            hit = self.prompts.get(params.get("name"))
            if not hit:
                return _error(mid, -32602, f"No prompt named {params.get('name')}")
            fn, desc = hit
            text = fn(**(params.get("arguments") or {}))
            result = {"description": desc, "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        elif method in ("resources/list", "resources/templates/list"):
            result = {"resources": []} if method == "resources/list" else {"resourceTemplates": []}
        else:
            return _error(mid, -32601, f"Method not found: {method}")
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def send(self, obj):
        line = json.dumps(obj, ensure_ascii=False, default=str)
        with self._write:
            self._out.write(line + "\n")
            self._out.flush()

    def _answer(self, msg):
        try:
            r = self.handle(msg)
        except Exception as e:                        # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            r = _error(msg.get("id"), -32603, f"{type(e).__name__}: {e}") if msg.get("id") is not None else None
        if r is not None:
            self.send(r)

    def run(self, stdin=None):
        """Serve until stdin closes. Anything the code prints goes to stderr: stdout is the protocol's."""
        stdin = stdin or sys.stdin
        sys.stdout = sys.stderr
        running = []
        for raw in stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                self.send(_error(None, -32700, "Parse error"))
                continue
            if msg.get("method") in ("initialize", "ping", "tools/list", "prompts/list"):
                self._answer(msg)                      # quick, and initialize must come first
            else:
                t = threading.Thread(target=self._answer, args=(msg,), daemon=True)
                t.start()
                running = [r for r in running if r.is_alive()] + [t]
        for t in running:                              # input closed: answer what was asked, then stop
            t.join()


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
