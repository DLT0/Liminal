import pytest
import os
import sys

# Add src folder to python path to import modules correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.suggestions_manager import _migrate_suggestions_schema
from src.podcast_library import _migrate_library_schema


def test_suggestions_migration():
    # Setup old schema input data
    old_data = {
        "items": [
            {
                "id": "item1",
                "title": "Old Suggestion 1",
                "category": "tech",
                "category_label": "Technology",
                "source_url": "https://example.com/1",
                "tags": ["python", "pytest"]
            },
            {
                "id": "item2",
                "title": "Old Suggestion 2",
                # category/category_label missing or None
                "source_url": "https://example.com/2",
                "playlist_id": "existing_playlist"
            }
        ],
        "categories": [{"id": "tech", "label": "Technology"}],
        "sections": []
    }

    # Perform migration
    new_data = _migrate_suggestions_schema(old_data)

    items = new_data["items"]
    assert len(items) == 2

    # Verify item 1
    item1 = items[0]
    assert "category" not in item1
    assert "category_label" not in item1
    assert item1["categories"] == ["tech"]
    assert item1["category_labels"] == ["Technology"]
    assert item1["playlist_id"] is None
    assert item1["title"] == "Old Suggestion 1"
    assert item1["source_url"] == "https://example.com/1"
    assert item1["tags"] == ["python", "pytest"]

    # Verify item 2
    item2 = items[1]
    assert "category" not in item2
    assert "category_label" not in item2
    assert item2["categories"] == []
    assert item2["category_labels"] == []
    assert item2["playlist_id"] == "existing_playlist"
    assert item2["title"] == "Old Suggestion 2"


def test_podcast_library_migration():
    # Setup old library schema input data
    old_data = {
        "items": [
            {
                "suggestion_id": "sug1",
                "title": "Library Item 1",
                "path": "/path/to/file1.mp3",
                "author": "Author 1"
            },
            {
                "suggestion_id": "sug2",
                "title": "Library Item 2",
                "path": "/path/to/file2.mp4",
                "listened_position": 12.5,
                "duration_seconds": 120.0,
                "last_played_at": "2026-07-14T00:00:00Z",
                "play_count": 2
            }
        ]
    }

    # Perform migration
    new_data = _migrate_library_schema(old_data)

    items = new_data["items"]
    assert len(items) == 2

    # Verify item 1 (which lacked the fields)
    item1 = items[0]
    assert item1["suggestion_id"] == "sug1"
    assert item1["title"] == "Library Item 1"
    assert item1["path"] == "/path/to/file1.mp3"
    assert item1["author"] == "Author 1"
    assert item1["listened_position"] == 0.0
    assert item1["duration_seconds"] == 0.0
    assert item1["last_played_at"] == ""
    assert item1["play_count"] == 0

    # Verify item 2 (which already had the fields, shouldn't be overwritten)
    item2 = items[1]
    assert item2["suggestion_id"] == "sug2"
    assert item2["title"] == "Library Item 2"
    assert item2["listened_position"] == 12.5
    assert item2["duration_seconds"] == 120.0
    assert item2["last_played_at"] == "2026-07-14T00:00:00Z"
    assert item2["play_count"] == 2


def test_playlist_and_category_retrieval(monkeypatch):
    import src.suggestions_manager as sm
    
    test_items = [
        {
            "id": "1",
            "title": "Episode 1",
            "categories": ["tech", "science"],
            "playlist_id": "pl1",
            "playlist_title": "Cool Tech Playlist",
            "season": 1,
            "episode": 1,
            "sort_order": 1
        },
        {
            "id": "2",
            "title": "Episode 2",
            "categories": ["tech"],
            "playlist_id": "pl1",
            "playlist_title": "Cool Tech Playlist",
            "season": 1,
            "episode": 2,
            "sort_order": 2
        },
        {
            "id": "3",
            "title": "Episode 3",
            "categories": ["science"],
            "playlist_id": "pl2",
            "playlist_title": "",
            "season": 2,
            "episode": 1,
            "sort_order": 3
        },
        {
            "id": "4",
            "title": "Independent Episode",
            "categories": ["tech"],
            "playlist_id": None,
            "season": 1,
            "episode": 1,
            "sort_order": 4
        }
    ]
    
    # Patch get_cached_items to return our test items
    monkeypatch.setattr(sm, "get_cached_items", lambda: test_items)
    
    # Test get_items_by_category
    tech_items = sm.get_items_by_category("tech")
    assert len(tech_items) == 3
    assert {i["id"] for i in tech_items} == {"1", "2", "4"}
    
    science_items = sm.get_items_by_category("science")
    assert len(science_items) == 2
    assert {i["id"] for i in science_items} == {"1", "3"}
    
    # Test get_items_by_playlist
    pl1_items = sm.get_items_by_playlist("pl1")
    assert len(pl1_items) == 2
    assert pl1_items[0]["id"] == "1"
    assert pl1_items[1]["id"] == "2"
    
    pl2_items = sm.get_items_by_playlist("pl2")
    assert len(pl2_items) == 1
    assert pl2_items[0]["id"] == "3"
    
    # Test get_playlists
    playlists = sm.get_playlists()
    assert len(playlists) == 2
    
    # pl1 playlist
    pl1 = next(p for p in playlists if p["playlist_id"] == "pl1")
    assert pl1["title"] == "Cool Tech Playlist"
    assert pl1["item_count"] == 2
    
    # pl2 playlist (playlist_title is empty, fallback to first item title "Episode 3")
    pl2 = next(p for p in playlists if p["playlist_id"] == "pl2")
    assert pl2["title"] == "Episode 3"
    assert pl2["item_count"] == 1


def test_import_youtube_playlist_invalid_url():
    from src.suggestions_manager import import_youtube_playlist
    with pytest.raises(ValueError) as excinfo:
        import_youtube_playlist("https://www.youtube.com/watch?v=123")
    assert "list=" in str(excinfo.value)


def test_import_youtube_playlist_success(monkeypatch):
    import src.suggestions_manager as sm
    
    # Mock yt_dlp
    class MockYoutubeDL:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def extract_info(self, url, download=False):
            return {
                "title": "Mock Playlist Title",
                "entries": [
                    {
                        "id": "vid1",
                        "title": "Mock Video 1",
                        "duration": 300,
                        "uploader": "Mock Creator",
                        "thumbnail": "https://img.com/1.jpg"
                    },
                    {
                        "id": "vid2",
                        "title": "Mock Video 2",
                        "duration": 600,
                        "uploader": "Mock Creator",
                        "thumbnail": "https://img.com/2.jpg"
                    }
                ]
            }
            
    import sys
    import types
    # Mock yt_dlp library
    mock_yt_dlp = types.ModuleType("yt_dlp")
    mock_yt_dlp.YoutubeDL = MockYoutubeDL
    sys.modules["yt_dlp"] = mock_yt_dlp
    
    # Mock _read_local_file and _write_local_file
    written_payloads = []
    monkeypatch.setattr(sm, "_read_local_file", lambda: {"items": []})
    monkeypatch.setattr(sm, "_write_local_file", lambda payload: written_payloads.append(payload))
    
    res = sm.import_youtube_playlist("https://www.youtube.com/playlist?list=PL123", "audio")
    
    assert res["playlist_title"] == "Mock Playlist Title"
    assert res["item_count"] == 2
    assert res["imported_count"] == 2
    assert res["playlist_id"].startswith("yt_")
    
    # Check that it wrote the items to the suggestions cache
    assert len(written_payloads) == 1
    items = written_payloads[0]["items"]
    assert len(items) == 2
    assert items[0]["id"] == "yt_vid1"
    assert items[0]["playlist_title"] == "Mock Playlist Title"
    assert items[0]["media_kind"] == "audio"
    assert items[0]["episode"] == 1

