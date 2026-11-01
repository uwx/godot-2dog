import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeEnvironment(dict):
    def AppendUnique(self, **values):
        for name, items in values.items():
            current = self.setdefault(name, [])
            current.extend(item for item in items if item not in current)

    def Append(self, **values):
        for name, items in values.items():
            self.setdefault(name, []).extend(items)

    def Prepend(self, **values):
        for name, items in values.items():
            self[name] = items + self.get(name, [])

    def Clone(self):
        return FakeEnvironment({name: list(value) if isinstance(value, list) else value for name, value in self.items()})


def environment(**values):
    # The keys every real SCons environment carries into sdl3_sources.build().
    return FakeEnvironment({"CCFLAGS": ["/fp:strict"], "CPPDEFINES": [], **values})


class Sdl3SourcesTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "sdl3_sources_under_test", Path(__file__).resolve().parents[1] / "sdl3_sources.py"
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"SCons": types.ModuleType("SCons"), "SCons.Errors": types.SimpleNamespace(UserError=RuntimeError)}):
            spec.loader.exec_module(self.module)

    def test_external_tree_supplies_every_source_from_its_own_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name in ("include/SDL3/SDL.h", "include/build_config/SDL_build_config_switch.h", "src/SDL.c", "src/video/sw.c"):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.touch()
            env = environment(
                sdl3_host="external",
                sdl3_external_root=directory,
                sdl3_external_sources="src/SDL.c src/video/sw.c",
            )
            sources, _ = self.module.build(env)
            self.assertEqual(sources, [str(root / "src" / "SDL.c"), str(root / "src" / "video" / "sw.c")])

    def test_external_tree_does_not_disable_its_own_subsystems(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "include").mkdir()
            env = environment(sdl3_host="external", sdl3_external_root=directory, sdl3_external_sources="src/SDL.c")
            _, env_sdl = self.module.build(env)
            self.assertNotIn("SDL_AUDIO_DISABLED", env_sdl["CPPDEFINES"])
            self.assertIn("SDL_MAIN_HANDLED", env_sdl["CPPDEFINES"])
            self.assertIn("SDL_BUILDING_LIBRARY", env_sdl["CPPDEFINES"])

    def test_external_tree_without_sources_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "include").mkdir()
            env = environment(sdl3_host="external", sdl3_external_root=directory, sdl3_external_sources="  ")
            with self.assertRaises(RuntimeError):
                self.module.build(env)

    def test_unknown_host_names_both_supported_configurations(self):
        env = environment(sdl3_host="mystery")
        with self.assertRaises(RuntimeError) as raised:
            self.module.build(env)
        self.assertIn("sdl3_host=external", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
