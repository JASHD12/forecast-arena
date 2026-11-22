"""T292: the S3 upload against moto's S3 implementation (boto3 calls are real, no AWS account).

Runs only where boto3 and moto are installed (the CI job `cloud`, or `.venv-cloud` locally), because
botocore needs python-dateutil < 3 and the main environment pins 4.x.
"""

import pytest

pytest.importorskip("boto3")
pytest.importorskip("moto")

import boto3
from moto import mock_aws

from arena.cloud.s3 import CACHE_HTML, CACHE_OTHER, content_type, upload_dir

BUCKET = "forecast-arena-site-test"


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-central-1"}
        )
        yield client


def site(tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    (tmp_path / "static" / "style.css").write_text("body{}")
    (tmp_path / "feed.xml").write_text("<feed/>")
    return tmp_path


def test_upload_sets_content_type_and_cache_headers(s3, tmp_path) -> None:
    rep = upload_dir(s3, BUCKET, site(tmp_path), "site")
    assert sorted(rep.uploaded) == ["site/feed.xml", "site/index.html", "site/static/style.css"]
    html = s3.head_object(Bucket=BUCKET, Key="site/index.html")
    assert html["ContentType"] == "text/html" and html["CacheControl"] == CACHE_HTML
    css = s3.head_object(Bucket=BUCKET, Key="site/static/style.css")
    assert css["ContentType"] == "text/css" and css["CacheControl"] == CACHE_OTHER
    assert s3.get_object(Bucket=BUCKET, Key="site/index.html")["Body"].read() == b"<h1>hi</h1>"


def test_a_second_upload_skips_unchanged_files_and_sends_changed_ones(s3, tmp_path) -> None:
    root = site(tmp_path)
    upload_dir(s3, BUCKET, root, "site")
    (root / "index.html").write_text("<h1>changed</h1>")
    rep = upload_dir(s3, BUCKET, root, "site")
    assert rep.uploaded == ["site/index.html"] and len(rep.skipped) == 2


def test_prune_and_dry_run(s3, tmp_path) -> None:
    root = site(tmp_path)
    upload_dir(s3, BUCKET, root, "site")
    (root / "feed.xml").unlink()
    dry = upload_dir(s3, BUCKET, root, "site", prune=True, dry_run=True)
    assert dry.deleted == ["site/feed.xml"]
    keys = {o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert "site/feed.xml" in keys  # nothing was deleted by the dry run
    upload_dir(s3, BUCKET, root, "site", prune=True)
    keys = {o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert "site/feed.xml" not in keys and "site/index.html" in keys


def test_other_prefixes_are_never_pruned(s3, tmp_path) -> None:
    s3.put_object(Bucket=BUCKET, Key="data/keep.parquet", Body=b"x")
    upload_dir(s3, BUCKET, site(tmp_path), "site", prune=True)
    assert s3.head_object(Bucket=BUCKET, Key="data/keep.parquet")


def test_content_types_and_input_checks(tmp_path) -> None:
    from pathlib import Path

    assert content_type(Path("a.json")) == "application/json"
    assert content_type(Path("a.unknownext")) == "application/octet-stream"
    with pytest.raises(ValueError):
        upload_dir(object(), "b", tmp_path / "missing")


def test_cli_publish_s3_uploads_a_built_directory(s3, tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from arena.cli import main

    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    (tmp_path / "built").mkdir()
    root = site(tmp_path / "built")
    args = ["--ledger-dir", str(tmp_path / "led"), "site", "publish-s3", "--bucket", BUCKET]
    res = CliRunner().invoke(main, [*args, "--dir", str(root), "--prefix", "p"])
    assert res.exit_code == 0, res.output
    assert "uploaded 3, skipped 0" in res.output
    again = CliRunner().invoke(main, [*args, "--dir", str(root), "--prefix", "p"])
    assert "uploaded 0, skipped 3" in again.output
