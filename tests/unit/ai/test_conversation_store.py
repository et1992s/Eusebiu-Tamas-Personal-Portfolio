from app.ai.conversation_store import ConversationStore

import os
import pickle
import threading

def test_conversation_store_initializes_new_session_with_system_prompt():
    store = ConversationStore()

    conversation = store.get_or_create(
        "session-1",
        "You are Zebios.",
    )

    assert conversation == [
        {
            "role": "system",
            "content": "You are Zebios.",
        }
    ]


def test_conversation_store_reuses_existing_session():
    store = ConversationStore()

    first = store.get_or_create(
        "session-1",
        "You are Zebios.",
    )

    first.append(
        {
            "role": "user",
            "content": "Hello",
        }
    )

    second = store.get_or_create(
        "session-1",
        "You are Zebios.",
    )

    assert second is first
    assert second == [
        {
            "role": "system",
            "content": "You are Zebios.",
        },
        {
            "role": "user",
            "content": "Hello",
        },
    ]


def test_conversation_store_keeps_sessions_isolated():
    store = ConversationStore()

    session_a = store.get_or_create(
        "session-a",
        "You are Zebios.",
    )

    session_b = store.get_or_create(
        "session-b",
        "You are Zebios.",
    )

    session_a.append(
        {
            "role": "user",
            "content": "Message A",
        }
    )

    assert session_a != session_b
    assert session_b == [
        {
            "role": "system",
            "content": "You are Zebios.",
        }
    ]

def test_conversation_store_reuses_lock_for_same_session():
    store = ConversationStore()

    first_lock = store.get_lock("session-1")
    second_lock = store.get_lock("session-1")

    assert second_lock is first_lock


def test_conversation_store_uses_separate_locks_for_different_sessions():
    store = ConversationStore()

    lock_a = store.get_lock("session-a")
    lock_b = store.get_lock("session-b")

    assert lock_a is not lock_b    

def test_conversation_store_saves_conversations_to_pickle(tmp_path):
    import pickle

    persistence_file = tmp_path / "chat_history.pkl"

    store = ConversationStore(
        conversations={
            "session-1": [
                {
                    "role": "system",
                    "content": "You are Zebios.",
                },
                {
                    "role": "user",
                    "content": "Hello",
                },
            ]
        }
    )

    store.save(persistence_file)

    assert persistence_file.exists()

    with open(persistence_file, "rb") as f:
        loaded = pickle.load(f)

    assert loaded == store.conversations    

def test_conversation_store_loads_conversations_from_pickle(tmp_path):
    import pickle

    persistence_file = tmp_path / "chat_history.pkl"

    conversations = {
        "session-1": [
            {
                "role": "system",
                "content": "You are Zebios.",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ]
    }

    with open(persistence_file, "wb") as f:
        pickle.dump(conversations, f)

    store = ConversationStore()

    loaded = store.load(persistence_file)

    assert loaded == conversations
    assert store.conversations == conversations    

def test_conversation_store_loads_empty_when_persistence_file_is_missing(tmp_path):
    persistence_file = tmp_path / "missing.pkl"

    store = ConversationStore(
        conversations={
            "session-1": [
                {
                    "role": "user",
                    "content": "Old data",
                }
            ]
        }
    )

    loaded = store.load(persistence_file)

    assert loaded == {}
    assert store.conversations == {}


def test_conversation_store_loads_empty_when_pickle_is_corrupted(tmp_path):
    persistence_file = tmp_path / "corrupted.pkl"

    with open(persistence_file, "wb") as f:
        f.write(b"this is not valid pickle data")

    store = ConversationStore()

    loaded = store.load(persistence_file)

    assert loaded == {}
    assert store.conversations == {}    

def test_conversation_store_serializes_concurrent_saves(tmp_path, monkeypatch):
    import threading
    import time

    persistence_file = tmp_path / "chat_history.pkl"

    store = ConversationStore(
        conversations={
            "session-1": [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ]
        }
    )

    active_saves = 0
    max_concurrent_saves = 0

    original_replace = __import__("os").replace

    def tracked_replace(source, destination):
        nonlocal active_saves, max_concurrent_saves

        active_saves += 1
        max_concurrent_saves = max(
            max_concurrent_saves,
            active_saves,
        )

        time.sleep(0.05)

        try:
            original_replace(source, destination)
        finally:
            active_saves -= 1

    monkeypatch.setattr("app.ai.conversation_store.os.replace", tracked_replace)

    thread_a = threading.Thread(
        target=store.save,
        args=(persistence_file,),
    )

    thread_b = threading.Thread(
        target=store.save,
        args=(persistence_file,),
    )

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert max_concurrent_saves == 1
    assert persistence_file.exists()