from ttp_similarity.api import __main__ as api_cli


def test_missing_dataset_without_auto_build_explains_what_to_run(capsys):
    assert api_cli.ensure_built("bos-calisma-alani", auto_build=False) is False
    out = capsys.readouterr().out
    assert "python -m ttp_similarity.data.build --dataset bos-calisma-alani" in out
    assert "--auto-build" in out


def test_cli_exits_with_code_2_when_artifacts_are_missing(capsys, monkeypatch):
    monkeypatch.setattr(api_cli.paths, "KNOWN_DATASETS", ("bos-calisma-alani",))
    assert api_cli.main(["--dataset", "bos-calisma-alani"]) == 2


def test_auto_build_builds_only_what_is_missing(monkeypatch):
    calls = []
    state = {"data": True, "engine": False}
    monkeypatch.setattr(api_cli.storage, "dataset_exists", lambda ws: state["data"])
    monkeypatch.setattr(api_cli.storage, "engine_exists", lambda ws: state["engine"])
    monkeypatch.setattr(api_cli.paths, "ensure_base_dirs", lambda: None)

    import ttp_similarity.data.build as data_build
    import ttp_similarity.engine.build as engine_build

    monkeypatch.setattr(data_build, "build_dataset", lambda name: calls.append(("data", name)))
    monkeypatch.setattr(engine_build, "build_engine", lambda name: calls.append(("engine", name)))

    assert api_cli.ensure_built("attck", auto_build=True) is True
    assert calls == [("engine", "attck")]
