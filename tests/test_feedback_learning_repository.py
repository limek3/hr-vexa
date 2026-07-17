from app.db.models import MatchFeedback
from app.db.repositories.messages import list_match_feedback_examples
from tests.factories import make_full_chain


async def test_list_match_feedback_examples_is_scoped_to_search(session):
    user, search, _source, message, match = await make_full_chain(
        session,
        telegram_user_id=401,
        source_ref="ref-feedback-learning-1",
        search_title="Candidate search",
    )
    other_user, other_search, _other_source, other_message, other_match = await make_full_chain(
        session,
        telegram_user_id=402,
        source_ref="ref-feedback-learning-2",
        search_title="Other search",
    )
    session.add_all(
        [
            MatchFeedback(
                user_id=user.id,
                match_id=match.id,
                search_id=search.id,
                message_id=message.id,
                is_relevant=False,
                message_text="Repeated vacancy template",
            ),
            MatchFeedback(
                user_id=other_user.id,
                match_id=other_match.id,
                search_id=other_search.id,
                message_id=other_message.id,
                is_relevant=True,
                message_text="Unrelated accepted message",
            ),
        ]
    )
    await session.flush()

    examples = await list_match_feedback_examples(session, search_id=search.id)

    assert examples == [("Repeated vacancy template", False)]
