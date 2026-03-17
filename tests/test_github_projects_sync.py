from app.services.github_projects_sync import ExistingDraft, _find_existing_draft_for_sync


def test_find_existing_draft_prefers_sync_key_match():
    draft = ExistingDraft(
        item_id="item-1",
        draft_issue_id="draft-1",
        title="个人 PC 客户端 release 形态完善",
        body="body",
        sync_key="plan:ready:pc-client",
    )

    found = _find_existing_draft_for_sync(
        existing_drafts={draft.sync_key: draft},
        sync_key="plan:ready:pc-client",
        title=draft.title,
        retained_item_ids=set(),
    )

    assert found == draft


def test_find_existing_draft_falls_back_to_unique_title_match():
    draft = ExistingDraft(
        item_id="item-2",
        draft_issue_id="draft-2",
        title="手机客户端与 mobile device 模板",
        body="body",
        sync_key="plan:in-progress:mobile-client",
    )

    found = _find_existing_draft_for_sync(
        existing_drafts={draft.sync_key: draft},
        sync_key="plan:done:mobile-client",
        title=draft.title,
        retained_item_ids=set(),
    )

    assert found == draft


def test_find_existing_draft_skips_title_match_if_already_retained():
    draft = ExistingDraft(
        item_id="item-3",
        draft_issue_id="draft-3",
        title="Current project context",
        body="body",
        sync_key="docs:current-context",
    )

    found = _find_existing_draft_for_sync(
        existing_drafts={draft.sync_key: draft},
        sync_key="docs:current-context-updated",
        title=draft.title,
        retained_item_ids={"item-3"},
    )

    assert found is None
