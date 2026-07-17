from app.services.filtering import analyze_match


def assert_rejected(text: str, keywords: list[str], minus_words: list[str] | None = None) -> None:
    result = analyze_match(text, keywords, minus_words or [])
    assert result.matched is False, result


def assert_accepted(text: str, keywords: list[str], minus_words: list[str] | None = None) -> None:
    result = analyze_match(text, keywords, minus_words or [])
    assert result.matched is True, result


def test_candidate_phrase_does_not_match_employer_synonyms():
    assert_rejected(
        "На сегодня к 13:00 нужен 1 грузчик. Работа с 10 до 18. Оплата 500 руб/час.",
        ["ищу работу"],
    )
    assert_rejected("Требуются грузчики. Работа на складе.", ["ищу работу"])
    assert_rejected("На постоянную работу ищем трех грузчиков.", ["ищу работу"])


def test_single_ischu_does_not_match_required_or_hashtag():
    assert_rejected("ТРЕБУЮТСЯ упаковщики. #ищуработу #вакансия #работа", ["ищу"])


def test_phrase_order_and_distance_are_respected():
    assert_rejected("Нужно пять человек. Сегодня работа на складе.", ["нужна работа"])
    assert_accepted("Мне срочно нужна работа грузчиком.", ["нужна работа"])


def test_candidate_messages_are_accepted():
    assert_accepted("Ищу работу грузчиком. Есть опыт 5 лет. Готов выйти завтра.", ["ищу работу"])
    assert_accepted("Ищу подработку грузчиком, могу приступить сегодня.", ["ищу работу"])
    assert_accepted("Грузчик ищет работу, Москва, опыт три года.", ["грузчик"])
    assert_accepted("Нужна работа водителем. Есть права категории B и личное авто.", ["водитель"])


def test_structured_order_template_is_rejected():
    assert_rejected(
        """№303790 👉 Валентин
Создано заказов: 1125
Зарегистрирован: 283 дня назад
Адрес: Москва
Фронт работы: разгрузка машины
Тариф: 400 руб. / час
Требуется 2 человека""",
        ["работа"],
    )


def test_vacancy_template_is_rejected_for_profession_search():
    assert_rejected(
        """УПАКОВЩИКИ ТАБАЧНЫХ ИЗДЕЛИЙ
Требуются упаковщики
Оплата 3400 ₽ смена
Обязанности: упаковка продукции
Мы предоставляем бесплатное проживание
По всем вопросам пишите менеджеру""",
        ["упаковщик"],
    )


def test_job_ad_without_required_word_is_rejected():
    assert_rejected(
        """Работа на складе. Адрес: Москва. Время: 12:00.
Оплата 400 руб/час по окончании смены. Для записи пишите в личные сообщения.""",
        ["работа"],
    )


def test_advertising_and_bot_spam_are_rejected_in_candidate_search():
    assert_rejected(
        "Хотите прорекламировать услуги? Мы разместим объявление. Подпишитесь на канал.",
        ["работа"],
    )


def test_usernames_urls_and_hashtags_do_not_satisfy_positive_keyword():
    assert_rejected("Вакансии: #ищуработу https://example.com @ischu_rabotu", ["ищу работу"])


def test_word_boundaries_and_conservative_morphology():
    assert_rejected("Пишите в личку, подключен автоответчик.", ["есть личный автомобиль"])
    assert_rejected("Работодатель приглашает сотрудников.", ["работал"])
    assert_rejected("Водитель10 публикует объявления.", ["водитель"])
    assert_accepted("Есть личный автомобиль, ищу работу курьером.", ["личный автомобиль"])


def test_minus_words_remain_strict_and_include_hashtags():
    assert_rejected("Ищу работу грузчиком. #агентство", ["ищу работу"], ["агентство"])
    assert_accepted("Ищу работу грузчиком. Есть опыт.", ["ищу работу"], ["агентство"])


def test_non_hr_searches_are_not_forced_through_employer_classifier():
    assert_accepted("Сдам квартиру с ремонтом на один месяц.", ["сдам квартирку"])
    assert_accepted("Ищу надежного поставщика мебели.", ["ищу поставщика"])


def test_explicit_vacancy_search_is_not_treated_as_candidate_search():
    assert_accepted("Открыта вакансия упаковщика. Требуются сотрудники.", ["вакансия"])


def test_service_ads_and_referral_posts_are_rejected():
    assert_rejected(
        "#помогу Работала в 15 нишах. Предлагаю услуги. Портфолио по ссылке.",
        ["работал"],
    )
    assert_rejected(
        "Разовая онлайн-подработка от рекламного агентства на партнерских заданиях.",
        ["ищу"],
    )


def test_vakhta_ads_and_external_group_invites_are_rejected():
    assert_rejected(
        "Вахта. Мужчины РФ/РБ до 55 лет. График 5/2. Общежитие. Медкнижка не нужна.",
        ["вахтой"],
    )
    assert_rejected(
        "Заходите в группу Работа Подработка Вахта: https://invite.viber.com/example",
        ["вахтой"],
    )


def test_candidate_with_schedule_and_desired_pay_is_not_rejected():
    assert_accepted(
        "Ищу работу упаковщиком. Готов выйти завтра. "
        "Рассмотрю график 6/1, оплата от 4000 за смену.",
        ["ищу работу"],
    )


def test_first_person_recruiter_phrases_are_not_mistaken_for_candidates():
    assert_rejected("Ищу пару людей на работу, подробности в лс.", ["ищу работу"])
    assert_rejected("Ищу людей на подработку. Выплаты ежедневно.", ["ищу"])
    assert_rejected(
        "Кто ищет ворк? Дам работу, выплаты каждый день, обслуживание оборудования.",
        ["ищу работу"],
    )
    assert_rejected("Ищу мастера для ремонта квартиры.", ["ищу"])


def test_candidate_search_requires_candidate_intent_not_just_a_generic_word():
    assert_rejected("Водитель нужен завтра к 10:00.", ["водитель"])
    assert_rejected("Работа, деньги, Москва. Пишите в личку.", ["работа"])
    assert_rejected(
        "Маош 110 000 руб. Иш графиги 6/1, турар жой ва овкат. Вахта.",
        ["вахтой"],
    )


def test_less_formal_candidate_wording_is_still_accepted():
    assert_accepted("Работал водителем пять лет. Рассмотрю предложения.", ["работал"])
    assert_accepted("Мы бригада из трех человек, ищем работу на стройке.", ["работа"])
    assert_accepted("Грузчик, опыт три года. Готов выйти завтра.", ["грузчик"])


def test_negative_feedback_rejects_a_similar_recurring_template():
    rejected_template = (
        "Ищу работу грузчиком. Опыт 5 лет, готов выйти завтра. Москва, связь в личных сообщениях."
    )
    result = analyze_match(
        "Ищу работу грузчиком. Опыт 6 лет, готов выйти сегодня. Москва, связь в личных сообщениях.",
        ["ищу работу"],
        [],
        feedback_examples=[(rejected_template, False)],
    )
    assert result.matched is False
    assert "Не подходит" in result.reason


def test_positive_feedback_can_teach_an_unusual_candidate_template():
    accepted_template = "Водитель категории B, свободен по будням, Москва и область."
    result = analyze_match(
        "Водитель категории B, свободен по будням, Москва и область.",
        ["водитель"],
        [],
        feedback_examples=[(accepted_template, True)],
    )
    assert result.matched is True
    assert "Подходит" in result.reason


def test_short_negative_feedback_does_not_become_a_global_minus_phrase():
    result = analyze_match(
        "Ищу работу грузчиком. Есть опыт, готов выйти завтра.",
        ["ищу работу"],
        [],
        feedback_examples=[("Ищу работу", False)],
    )
    assert result.matched is True
