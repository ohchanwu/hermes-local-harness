"""Offline tests for plugins/jev/tool_filter.py (Part B of the jev plugin).

transform() is called directly with a fake `ask` function (no network, no
TypeSafe call) and a `log` function that writes JSON lines into a temporary
directory. Every tool output, argument and path is synthetic.
"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plugins/jev/tool_filter.py"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(module_spec)
    loader.exec_module(module)
    return module


tool_filter = load("jev_tool_filter_under_test", MODULE)

SENTINEL = "SENTINEL-OUTPUT-4d1c9e"
ARG_SENTINEL = "SENTINEL-ARGUMENT-82fb03"

SETTINGS = {
    "enabled": True,
    "tools": ["terminal", "execute_code", "search_files", "browser_exec"],
    "min_chars": 8000,
    "max_chars": 100000,
    "chunk_lines": 40,
    "chunk_chars": 2000,
    "args_chars": 2000,
    "keep_threshold": 0.3,
    "max_kept_ratio": 0.8,
}


class FakeAnswer:
    def __init__(self, answers, input_tokens=1234, latency_ms=87):
        self.answers = answers
        self.input_tokens = input_tokens
        self.output_tokens = 0
        self.latency_ms = latency_ms


class FakeJevError(Exception):
    error_class = "JevTimeout"


class FakeAsk:
    """Records each call; answers each chunk question with probability(n, total)."""

    def __init__(self, probability=None, raise_exc=None, answers=None):
        self.probability = probability or (lambda n, total: 0.0)
        self.raise_exc = raise_exc
        self.answers = answers
        self.calls = []

    def __call__(self, state, questions):
        self.calls.append((state, questions))
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.answers is not None:
            return FakeAnswer(self.answers)
        total = len(questions)
        return FakeAnswer({
            name: {"noul": self.probability(int(name.split("_")[1]), total)} for name in questions
        })


def make_text(lines=400, width=40, marker=SENTINEL):
    """400 lines of 41 characters with the newline: ten chunks of 40 lines."""
    rows = []
    for n in range(1, lines + 1):
        body = f"line {n:04d} {marker} é "
        rows.append((body + "x" * width)[:width])
    return "\n".join(rows) + "\n"


class FilterTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.log_dir = self.tmp / "logs"
        self.cache_dir = self.tmp / "home" / "cache" / "jev"

    def tearDown(self):
        # The sentinel placed in tool output and arguments must not reach any log file.
        if self.log_dir.exists():
            for path in self.log_dir.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8")
                    self.assertNotIn(SENTINEL, content, path)
                    self.assertNotIn(ARG_SENTINEL, content, path)
        self._tmp.cleanup()

    def log(self, stream, record):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / f"{stream}.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def records(self, stream="tool_results"):
        path = self.log_dir / f"{stream}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def run_transform(self, tool_name, result, ask, args=None, settings=None):
        return tool_filter.transform(
            tool_name=tool_name,
            args={"command": f"run-something {ARG_SENTINEL}"} if args is None else args,
            result=result, session_id="session-1", profile="example-worker",
            settings=SETTINGS if settings is None else settings, ask=ask, log=self.log,
            cache_dir=str(self.cache_dir))

    def saved_files(self):
        return sorted(self.cache_dir.glob("*.txt")) if self.cache_dir.exists() else []


class FilteredResultTests(FilterTestCase):
    def test_terminal_result_filtered_and_other_fields_preserved(self):
        text = make_text()
        original = {"output": text, "exit_code": 2, "error": None,
                    "hint": "keep this hint", "exit_code_meaning": "failure é"}
        result = json.dumps(original, ensure_ascii=False)
        ask = FakeAsk(lambda n, total: 0.9 if n == 5 else 0.05)

        new = self.run_transform("terminal", result, ask)

        self.assertIsInstance(new, str)
        parsed = json.loads(new)
        self.assertEqual(list(parsed), list(original))
        for key in original:
            if key != "output":
                self.assertEqual(parsed[key], original[key])
        # Every byte outside the output value is unchanged.
        self.assertEqual(new.replace(json.dumps(parsed["output"], ensure_ascii=False), "@"),
                         result.replace(json.dumps(text, ensure_ascii=False), "@"))
        chunks = tool_filter._make_chunks(text, 40, 2000)
        output = parsed["output"]
        self.assertTrue(output.startswith(chunks[0]))
        self.assertTrue(output.endswith(chunks[-1]))
        self.assertIn(chunks[4], output)
        self.assertNotIn(chunks[1], output)
        self.assertLess(len(output), 0.8 * len(text))

        saved = self.saved_files()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(encoding="utf-8"), text)
        self.assertRegex(saved[0].name, r"^\d{8}T\d{6}Z-terminal-[0-9a-f]{8}\.txt$")
        self.assertEqual(stat.S_IMODE(saved[0].stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.cache_dir.stat().st_mode), 0o700)

        removal_lines = [line for line in output.splitlines() if line.startswith("[jev: ")]
        self.assertEqual(len(removal_lines), 2)  # chunks 2-4 and chunks 6 to last-1
        for line in removal_lines:
            self.assertIn(str(saved[0]), line)
        self.assertIn("[jev: 120 lines removed here; the full output is saved in", removal_lines[0])

        (record,) = self.records()
        self.assertEqual(record["event"], "filter")
        self.assertEqual(record["action"], "filtered")
        self.assertEqual(record["tool"], "terminal")
        self.assertEqual(record["profile"], "example-worker")
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["chars_before"], len(text))
        self.assertEqual(record["chars_after"], len(output))
        self.assertEqual(record["chunks_total"], len(chunks))
        self.assertEqual(record["chunks_kept"], 3)
        self.assertEqual(record["jev_latency_ms"], 87)
        self.assertEqual(record["jev_input_tokens"], 1234)
        self.assertIsNone(record["error_class"])
        self.assertEqual(record["saved_file"], str(saved[0]))
        self.assertEqual(set(record), set(tool_filter.RECORD_FIELDS))

    def test_one_request_with_one_noul_question_per_chunk(self):
        text = make_text()
        long_args = {"command": ARG_SENTINEL + "a" * 5000}
        ask = FakeAsk()
        self.run_transform("execute_code", json.dumps({"status": "success", "output": text}), ask,
                           args=long_args)
        self.assertEqual(len(ask.calls), 1)
        state, questions = ask.calls[0]
        self.assertEqual(state["tool"], "execute_code")
        self.assertEqual(len(state["arguments"]), 2000)
        self.assertEqual("".join(state["chunks"][str(n)] for n in range(1, len(state["chunks"]) + 1)),
                         text)
        for chunk in state["chunks"].values():
            self.assertLessEqual(len(chunk), 2000)
            self.assertLessEqual(len(chunk.splitlines()), 40)
        self.assertEqual(len(questions), len(state["chunks"]))
        self.assertEqual(questions["chunk_3"]["type"], "noul")
        self.assertEqual(questions["chunk_3"]["instructions"],
                         "Does chunk 3 of the tool output in `state` contain an error, a failure, "
                         "a warning, a result value, or other information needed to continue the "
                         "work the command was run for?")

    def test_long_line_split_to_chunk_chars(self):
        text = ("y" * 30000) + "\n" + make_text(lines=10)
        ask = FakeAsk()
        self.run_transform("terminal", json.dumps({"output": text, "exit_code": 0}), ask)
        state, _questions = ask.calls[0]
        self.assertTrue(all(len(chunk) <= 2000 for chunk in state["chunks"].values()))
        self.assertEqual("".join(state["chunks"].values()), text)

    def test_first_and_last_chunks_always_kept(self):
        text = make_text()
        ask = FakeAsk(lambda n, total: 0.0)
        new = self.run_transform("browser_exec",
                                 json.dumps({"success": True, "exit_code": 0, "output": text}), ask)
        output = json.loads(new)["output"]
        chunks = tool_filter._make_chunks(text, 40, 2000)
        self.assertEqual(output, chunks[0] + "[jev: "
                         f"{sum(len(c.splitlines()) for c in chunks[1:-1])} lines removed here; the full "
                         f"output is saved in {self.saved_files()[0]}]\n" + chunks[-1])
        self.assertEqual(self.records()[0]["chunks_kept"], 2)

    def test_search_files_matches_text_filtered(self):
        text = make_text()
        result = json.dumps({"total_count": 400, "matches_format": "path-grouped",
                             "matches_text": text, "truncated": True}, ensure_ascii=False)
        new = self.run_transform("search_files", result, FakeAsk())
        parsed = json.loads(new)
        self.assertEqual(parsed["total_count"], 400)
        self.assertTrue(parsed["truncated"])
        self.assertLess(len(parsed["matches_text"]), len(text))

    def test_ascii_escaped_serialization_is_kept(self):
        text = make_text()
        result = json.dumps({"output": text, "exit_code": 0})  # ensure_ascii=True
        new = self.run_transform("terminal", result, FakeAsk())
        self.assertIsNotNone(new)
        self.assertNotIn("é", new)
        self.assertIn("\\u00e9", new)


class UnchangedResultTests(FilterTestCase):
    def assert_unchanged(self, value, ask):
        self.assertIsNone(value)
        self.assertEqual(ask.calls, [])
        self.assertEqual(self.saved_files(), [])

    def test_unrecognised_formats_unchanged(self):
        text = make_text()
        for result in (text, json.dumps([text]), json.dumps({"stdout": text}),
                       json.dumps({"output": 12}), None,
                       {"_multimodal": True, "text_summary": text}):
            ask = FakeAsk()
            self.assert_unchanged(self.run_transform("terminal", result, ask), ask)
        self.assertEqual({r["reason"] for r in self.records()}, {"unrecognised_format"})
        self.assertEqual({r["action"] for r in self.records()}, {"skipped"})

    def test_search_files_without_matches_text_unchanged(self):
        result = json.dumps({"total_count": 500, "files": [f"/tmp/f{n}" for n in range(1000)]})
        ask = FakeAsk()
        self.assert_unchanged(self.run_transform("search_files", result, ask), ask)

    def test_below_min_and_above_max_skipped(self):
        for size, reason in ((8000, "below_min_chars"), (100001, "above_max_chars")):
            ask = FakeAsk()
            text = ("z" * 99 + "\n") * (size // 100) + "q" * (size % 100)
            self.assertEqual(len(text), size)
            self.assert_unchanged(
                self.run_transform("terminal", json.dumps({"output": text, "exit_code": 0}), ask), ask)
            record = self.records()[-1]
            self.assertEqual((record["action"], record["reason"], record["chars_before"]),
                             ("skipped", reason, size))

    def test_at_max_chars_is_filtered(self):
        text = ("z" * 99 + "\n") * 1000
        self.assertEqual(len(text), 100000)
        self.assertIsNotNone(self.run_transform("terminal", json.dumps({"output": text}), FakeAsk()))

    def test_kept_ratio_at_or_above_max_unchanged(self):
        text = make_text()
        total = len(tool_filter._make_chunks(text, 40, 2000))
        for probability in (lambda n, t: 0.9, lambda n, t: 0.9 if n <= int(t * 0.85) else 0.0):
            ask = FakeAsk(probability)
            self.assertIsNone(self.run_transform("terminal", json.dumps({"output": text}), ask))
            self.assertEqual(len(ask.calls), 1)
        self.assertEqual(self.saved_files(), [])
        for record in self.records():
            self.assertEqual((record["action"], record["reason"]),
                             ("unchanged", "kept_ratio_at_or_above_max"))
            self.assertEqual(record["chunks_total"], total)
            self.assertIsNone(record["saved_file"])

    def test_read_file_and_kanban_tools_never_filtered(self):
        text = make_text()
        settings = dict(SETTINGS, tools=SETTINGS["tools"] + ["read_file", "kanban_show"])
        result = json.dumps({"output": text, "content": text})
        for tool_name in ("read_file", "kanban_show", "kanban_list"):
            ask = FakeAsk()
            self.assert_unchanged(
                self.run_transform(tool_name, result, ask, args={"path": "/tmp/x"},
                                   settings=settings), ask)
        self.assertEqual(self.records(), [])

    def test_tool_not_listed_or_section_disabled(self):
        text = make_text()
        ask = FakeAsk()
        result = json.dumps({"output": text})
        self.assert_unchanged(self.run_transform("process", result, ask), ask)
        self.assert_unchanged(self.run_transform("terminal", result, ask,
                                                 settings=dict(SETTINGS, tools=["execute_code"])), ask)
        self.assert_unchanged(self.run_transform("terminal", result, ask,
                                                 settings=dict(SETTINGS, enabled=False)), ask)

    def test_jev_error_leaves_result_unchanged(self):
        text = make_text()
        result = json.dumps({"output": text, "exit_code": 0})
        cases = (
            (FakeAsk(raise_exc=FakeJevError("timed out")), "JevTimeout"),
            (FakeAsk(raise_exc=ValueError("bad")), "ValueError"),
            (FakeAsk(answers={"chunk_1": {"noul": 0.5}}), "UnexpectedAnswer"),
            (FakeAsk(answers={f"chunk_{n}": {"noul": 1.5} for n in range(1, 200)}), "UnexpectedAnswer"),
            (FakeAsk(answers=["not", "a", "dict"]), "UnexpectedAnswer"),
        )
        for ask, error_class in cases:
            self.assertIsNone(self.run_transform("terminal", result, ask))
            record = self.records()[-1]
            self.assertEqual((record["action"], record["reason"], record["error_class"]),
                             ("unchanged", "jev_error", error_class))
            self.assertIsNone(record["saved_file"])
        self.assertEqual(self.saved_files(), [])

    def test_never_raises(self):
        def broken_log(stream, record):
            raise OSError("disk full")

        text = make_text()
        value = tool_filter.transform(
            tool_name="terminal", args=None, result=json.dumps({"output": text}),
            session_id=None, profile=None, settings=SETTINGS,
            ask=FakeAsk(raise_exc=RuntimeError("x")), log=broken_log, cache_dir=str(self.cache_dir))
        self.assertIsNone(value)
        value = tool_filter.transform(
            tool_name=None, args=object(), result=object(), session_id=object(), profile=None,
            settings=None, ask=None, log=broken_log, cache_dir=None)
        self.assertIsNone(value)
        # cache_dir that cannot be created: the error is logged, the result is unchanged.
        blocker = self.tmp / "file-not-dir"
        blocker.write_text("x", encoding="utf-8")
        value = tool_filter.transform(
            tool_name="terminal", args={}, result=json.dumps({"output": text}),
            session_id="s", profile="p", settings=SETTINGS, ask=FakeAsk(), log=self.log,
            cache_dir=str(blocker / "jev"))
        self.assertIsNone(value)
        self.assertEqual(self.records()[-1]["reason"], "internal_error")


class SavedReadTests(FilterTestCase):
    def test_read_of_saved_file_is_logged(self):
        text = make_text()
        self.run_transform("terminal", json.dumps({"output": text}), FakeAsk())
        (saved,) = self.saved_files()
        ask = FakeAsk()
        self.assertIsNone(self.run_transform("read_file", json.dumps({"content": text}), ask,
                                             args={"path": str(saved), "offset": 41}))
        self.assertEqual(ask.calls, [])
        record = self.records()[-1]
        self.assertEqual(record["event"], "saved_read")
        self.assertEqual(record["tool"], "read_file")
        self.assertEqual(record["saved_file"], os.path.realpath(saved))
        self.assertEqual(record["session_id"], "session-1")

    def test_read_outside_cache_dir_not_logged(self):
        self.cache_dir.mkdir(parents=True)
        outside = self.tmp / "other.txt"
        for path in (str(outside), str(self.cache_dir), str(self.cache_dir) + "-other/x.txt"):
            self.assertIsNone(self.run_transform("read_file", "{}", FakeAsk(), args={"path": path}))
        self.assertEqual(self.records(), [])


if __name__ == "__main__":
    unittest.main()
