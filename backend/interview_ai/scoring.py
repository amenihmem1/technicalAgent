from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from interview_ai.constants import SKILL_KEYS
from interview_ai.prompts import build_chat_messages, build_cv_summary


RequestJsonFn = Callable[..., dict[str, Any]]
NormalizeScoresFn = Callable[[Any], dict[str, int]]

TRIVIAL_LAUNCH_MESSAGES = {
    "je suis prete",
    "je suis pret",
    "je suis prete de commencer",
    "je suis pret de commencer",
    "prete",
    "pret",
    "prete de commencer",
    "pret de commencer",
    "ready",
    "ready to start",
    "i am ready",
    "i am ready to start",
    "im ready",
    "im ready to start",
    "oui",
    "ok",
    "d accord",
    "bonjour",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("'", " ")
    return " ".join(normalized.lower().split()).strip()


def _is_trivial_launch_message(text: str) -> bool:
    return _normalize_text(text) in TRIVIAL_LAUNCH_MESSAGES


def _has_meaningful_scores(scores: dict[str, int]) -> bool:
    return any(int(scores.get(key, 0)) > 0 for key in SKILL_KEYS)


def _empty_turn_scoring_payload() -> dict[str, Any]:
    score_partial = {key: 0 for key in SKILL_KEYS}
    return {
        "score_partial": score_partial,
    }


def _normalize_turn_scoring_payload(
    parsed: dict[str, Any],
    normalize_scores: NormalizeScoresFn,
) -> dict[str, Any]:
    if isinstance(parsed, dict) and isinstance(parsed.get("score_partial"), dict):
        score_partial = normalize_scores(parsed.get("score_partial"))
        return {
            "score_partial": score_partial,
        }

    score_partial = normalize_scores(parsed if isinstance(parsed, dict) else {})
    return {
        "score_partial": score_partial,
    }


def _heuristic_competency_scores(history_text: str) -> dict[str, int]:
    normalized = _normalize_text(history_text)
    searchable = f" {normalized} "
    word_count = len(re.findall(r"\b[\w'-]+\b", normalized, flags=re.UNICODE))

    question_score = 1 if word_count >= 25 else 0

    if any(marker in searchable for marker in (" architecture ", " conception ", " design ", " couche ", " module ", " composant ", " pipeline ")):
        question_score = max(question_score, 3)
    if any(marker in searchable for marker in (" microservice ", " api ", " backend ", " frontend ", " base de donnees ", " database ")):
        question_score = max(question_score, 4)

    if any(marker in searchable for marker in (" optimisation ", " optimiser ", " performance ", " scalabil", " latence ", " cache ", " throughput ")):
        question_score = max(question_score, 3)
    if any(marker in searchable for marker in (" complexite ", " charge ", " distribue ", " scaling ", " batch ", " temps reel ")):
        question_score = max(question_score, 4)

    if any(marker in searchable for marker in (" bug ", " erreur ", " exception ", " debug", " diagnostic ", " logs ", " trace ")):
        question_score = max(question_score, 3)
    if any(marker in searchable for marker in (" test ", " reproduire ", " root cause ", " cause racine ", " monitoring ")):
        question_score = max(question_score, 4)

    if any(marker in searchable for marker in (" ia ", " intelligence artificielle ", " machine learning ", " deep learning ", " modele ", " reseau de neurones ")):
        question_score = max(question_score, 3)
    if any(marker in searchable for marker in (" transformer ", " attention ", " llm ", " embedding ", " rag ", " fine tuning ", " prompt ")):
        question_score = max(question_score, 4)

    return {"question_score": min(4, question_score)}


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    searchable = f" {text} "
    return any(marker in searchable or marker.strip() in text for marker in markers)


def _concept_group_score(answer_text: str, groups: tuple[tuple[str, ...], ...]) -> int:
    return sum(1 for markers in groups if _contains_any(answer_text, markers))


def _heuristic_question_answer_score(question: str, answer: str) -> int:
    """Course-aware guardrail for good oral answers that the LLM underrates.

    The speech-to-text layer can produce noisy words ("non-reputation" for
    "non-repudiation", etc.). This scorer looks for concept coverage rather
    than exact phrasing and is only used as a floor for non-empty answers.
    """
    normalized_question = _normalize_text(question)
    normalized_answer = _normalize_text(answer)
    if not normalized_answer or _is_trivial_launch_message(normalized_answer):
        return 0

    word_count = len(re.findall(r"\b[\w'-]+\b", normalized_answer, flags=re.UNICODE))
    score = 1 if word_count >= 12 else 0
    if word_count >= 35:
        score = max(score, 2)

    if "blockchain" in normalized_question and (
        ("non" in normalized_question and "repudiation" in normalized_question)
        or ("non" in normalized_question and "reputation" in normalized_question)
        or "non-r?pudiation" in normalized_question
        or "non-r?putation" in normalized_question
        or "non r?pudiation" in normalized_question
        or "non r?putation" in normalized_question
        or "non repudiation" in normalized_question
        or "non-repudiation" in normalized_question
        or "non reputation" in normalized_question
        or "non-reputation" in normalized_question
    ):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" cryptographie asymetrique ", " cryptographie asym ", " asymetrique ", " asym?trique ", " cle publique ", " cle privee ", " cl? priv?e "),
                (" signature numerique ", " signatures numeriques ", " signature num?rique ", " signatures num?riques ", " signee ", " sign?e ", " signe "),
                (" identite ", " identit? ", " authenticite ", " prouve ", " emetteur ", " utilisateur "),
                (" immuable ", " inalterable ", " modifier ", " modifi?e ", " supprimee ", " supprim?e ", " supprime ", " bloc "),
                (" nier ", " ne peut pas nier ", " non repudiation ", " non reputation "),
            ),
        )
        if coverage >= 4:
            return 4
        if coverage >= 3:
            return 3

    if "blockchain" in normalized_question and ("bloc" in normalized_question or "hash" in normalized_question or "hachage" in normalized_question):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" bloc ", " blocs "),
                (" transaction ", " transactions "),
                (" hash ", " hachage ", " hachages ", " empreinte "),
                (" precedent ", " precedente ", " chaine ", " chainage "),
                (" modifier ", " modifie ", " chang", " invalide ", " integrite ", " securis"),
                (" consensus ", " noeud ", " noeuds ", " reseau ", " validation "),
            ),
        )
        if coverage >= 5 and word_count >= 45:
            return 4
        if coverage >= 4:
            return 3

    if "blockchain" in normalized_question and (
        "noeud" in normalized_question or "nœud" in normalized_question or "n?ud" in normalized_question
    ):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" noeud ", " noeuds ", " nœud ", " nœuds ", " node ", " nodes "),
                (" ordinateur ", " appareil ", " connecte ", " reseau "),
                (" copie ", " stocke ", " blockchain totale ", " blockchain partielle "),
                (" valide ", " valider ", " transactions ", " blocs "),
                (" transmet ", " propage ", " autres noeuds "),
                (" full node ", " noeud complet ", " lightnode ", " light node ", " noeud leger "),
                (" decentralise ", " entite centrale ", " controle "),
            ),
        )
        if coverage >= 5 and word_count >= 55:
            return 4
        if coverage >= 4:
            return 3

    if "bitcoin" in normalized_question and (
        "monnaie" in normalized_question or "emission" in normalized_question or "classique" in normalized_question
    ):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" monnaie ", " monnaies ", " fiat ", " classique "),
                (" banque centrale ", " banques centrales "),
                (" emettre ", " emission ", " creer ", " creation "),
                (" discretionnaire ", " flexibilite ", " controlee ", " reagir ", " crise "),
                (" bitcoin ", " rarete ", " previsibilite ", " mathematique ", " limite "),
                (" inflation ", " masse monetaire ", " politique monetaire "),
            ),
        )
        if coverage >= 5 and word_count >= 45:
            return 4
        if coverage >= 4:
            return 3

    if "machine learning" in normalized_question and ("exemple" in normalized_question or "application" in normalized_question):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" recommandation ", " recommande ", " netflix ", " youtube "),
                (" comportement ", " videos regardees ", " contenu aime ", " utilisateurs "),
                (" modele ", " modeles ", " apprend ", " analysent ", " analyser "),
                (" similaire ", " interesse ", " automatiquement ", " prediction "),
            ),
        )
        if coverage >= 3:
            return 4
        if coverage >= 2:
            return 3

    if "blockchain" in normalized_question and ("scalabil" in normalized_question or "transactions" in normalized_question):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" nombre limite ", " limite ", " transactions par seconde ", " tps "),
                (" validee ", " valid?e ", " valider ", " reseau ", " r?seau ", " reseaux ", " r?seaux ", " noeuds ", " consensus "),
                (" bloc ", " enregistree ", " chaine "),
                (" ralentir ", " delai ", " d?lai ", " confirmation ", " frais ", " charge "),
            ),
        )
        if coverage >= 3:
            return 4
        if coverage >= 2 and word_count >= 35:
            return 4
        if coverage >= 2:
            return 3

    if (
        "machine learning" in normalized_question
        and "fraude" in normalized_question
        and "blockchain" in normalized_question
    ):
        coverage = _concept_group_score(
            normalized_answer,
            (
                (" comportement suspect ", " comportements suspects ", " anomalies ", " inhabituel ", " inhabituels ", " inhabitu?s "),
                (" transactions repetitives ", " repetitives ", " montants anormaux ", " adresses suspectes "),
                (" modele ", " mod?le ", " modeles ", " mod?les ", " apprendre ", " reconnaitre ", " reconna?tre ", " analyser automatiquement "),
                (" scalabilite ", " scalabilit? ", " charge ", " performance ", " ralentir "),
                (" hors chaine ", " hors cha?ne ", " off chain ", " off-chain ", " a risque ", " optimise ", " optimis?e "),
            ),
        )
        if coverage >= 4:
            return 4
        if coverage >= 3 and word_count >= 45:
            return 4
        if coverage >= 3:
            return 3

    heuristic = _heuristic_competency_scores(f"Q: {question}\nR: {answer}").get("question_score", 0)
    return max(score, heuristic)


def _apply_heuristic_floor(
    score_payload: dict[str, int],
    *,
    question: str,
    answer: str,
) -> dict[str, int]:
    adjusted = dict(score_payload)
    heuristic_score = _heuristic_question_answer_score(question, answer)
    current_score = int(adjusted.get("question_score", 0) or 0)
    if heuristic_score > current_score:
        adjusted["question_score"] = heuristic_score
    return adjusted


def score_interview_turn(
    *,
    request_json: RequestJsonFn,
    normalize_scores: NormalizeScoresFn,
    cv_profile: dict[str, Any],
    recent_turns: list[dict[str, Any]],
    question: str,
    answer: str,
    question_phase: str,
    response_language: str = "fr",
) -> dict[str, Any]:
    cleaned_answer = str(answer or "").strip()
    if not cleaned_answer or _is_trivial_launch_message(cleaned_answer):
        return _empty_turn_scoring_payload()

    question = str(question or "").strip()
    phase = str(question_phase or "").strip().upper() or "INTRO"
    cv_summary = build_cv_summary(cv_profile) if isinstance(cv_profile, dict) else "Profil CV non disponible."

    history_lines: list[str] = []
    for turn in recent_turns[-3:]:
        if not isinstance(turn, dict):
            continue
        previous_question = str(turn.get("say", "")).strip()[:140]
        previous_answer = str(turn.get("candidate_text", "")).strip()[:220]
        if previous_question or previous_answer:
            history_lines.append(f"Q: {previous_question}\nR: {previous_answer}")
    history_text = "\n\n".join(history_lines) if history_lines else "Aucun historique exploitable."
    turn_text = f"Q: {question[:180] or 'Aucune question precedente'}\nR: {cleaned_answer[:420]}"

    if response_language == "en":
        system = (
            "You are a dedicated technical interview scoring tool. "
            "Score only the candidate answer to the last interviewer question. "
            "Reply ONLY with valid JSON."
        )
        user = (
            "Grade this single answer from 0 to 5 like a teacher grading an exam answer about the course.\n"
            "Use 0 only when the answer is empty, off-topic, or unusable.\n"
            "Do not over-penalize oral transcription mistakes when the key concepts are present.\n"
            "Rubric: 1=very weak but related, 2=partial idea, 3=mostly correct, 4=correct and explained, 5=excellent and complete.\n"
            "Return ONLY this JSON:\n"
            '{"score_partial":{"question_score":0}}\n\n'
            f"Question phase:\n{phase}\n\n"
            f"CV summary:\n{cv_summary}\n\n"
            f"Recent context:\n{history_text}\n\n"
            f"Answer to score:\n{turn_text}"
        )
    else:
        system = (
            "Tu es un outil de scoring dedie a l'entretien technique. "
            "Tu notes uniquement la reponse du candidat a la derniere question posee. "
            "Reponds UNIQUEMENT avec un JSON valide."
        )
        user = (
            "Note cette seule reponse de 0 a 5 comme un professeur qui corrige une reponse d'examen sur le cours.\n"
            "Utilise 0 uniquement si la reponse est vide, hors sujet ou inexploitable.\n"
            "Ne penalise pas fortement les erreurs de transcription orale si les concepts cles sont presents.\n"
            "Bareme: 1=tres faible mais relie, 2=idee partielle, 3=globalement correct, 4=correct et explique, 5=excellent et complet.\n"
            "Retourne UNIQUEMENT ce JSON :\n"
            '{"score_partial":{"question_score":0}}\n\n'
            f"Phase de la question :\n{phase}\n\n"
            f"Resume CV :\n{cv_summary}\n\n"
            f"Contexte recent :\n{history_text}\n\n"
            f"Reponse a noter :\n{turn_text}"
        )

    parsed = request_json(
        messages=build_chat_messages(
            system_content=system,
            user_content=user,
        ),
        max_tokens=260,
        temperature=0.1,
        log_mode="score_turn_prompt_json",
        phase=phase,
    )
    normalized = _normalize_turn_scoring_payload(parsed, normalize_scores)
    normalized["score_partial"] = _apply_heuristic_floor(
        normalized["score_partial"],
        question=question,
        answer=cleaned_answer,
    )
    if _has_meaningful_scores(normalized["score_partial"]):
        return normalized

    retry = request_json(
        messages=build_chat_messages(
            system_content=system,
            user_content=(
                f"{user}\n\n"
                "La reponse precedente etait trop conservative. "
                "Reevalue cette reponse tour par tour et attribue un score non nul des qu'il existe "
                "une reponse techniquement correcte, partiellement correcte ou appliquee au cours."
            ),
        ),
        max_tokens=300,
        temperature=0.05,
        log_mode="score_turn_prompt_json_retry",
        phase=phase,
    )
    normalized_retry = _normalize_turn_scoring_payload(retry, normalize_scores)
    normalized_retry["score_partial"] = _apply_heuristic_floor(
        normalized_retry["score_partial"],
        question=question,
        answer=cleaned_answer,
    )
    if _has_meaningful_scores(normalized_retry["score_partial"]):
        return normalized_retry

    heuristic_scores = {
        "question_score": _heuristic_question_answer_score(question, cleaned_answer),
    }
    return {
        "score_partial": heuristic_scores,
    }


def infer_competencies_from_interview(
    *,
    request_json: RequestJsonFn,
    normalize_scores: NormalizeScoresFn,
    cv_profile: dict[str, Any],
    turns: list[dict[str, Any]],
    response_language: str = "fr",
) -> dict[str, int]:
    history_lines: list[str] = []
    for turn in turns[-6:]:
        if not isinstance(turn, dict):
            continue
        question = str(turn.get("say", "")).strip()[:160]
        answer = str(turn.get("candidate_text", "")).strip()[:320]
        if _is_trivial_launch_message(answer):
            continue
        if question or answer:
            history_lines.append(f"Q: {question}\nR: {answer}")

    history_text = "\n\n".join(history_lines) if history_lines else "Aucun historique exploitable."
    cv_summary = build_cv_summary(cv_profile) if isinstance(cv_profile, dict) else "Profil CV non disponible."

    if response_language == "en":
        system = (
            "You are a senior technical interviewer. "
            "Assess the candidate only from the interview excerpts and CV summary. "
            "Reply ONLY with a valid JSON object."
        )
        user = (
            "Return the average exam grade from 0 to 5 for the candidate's answers.\n"
            "Use 0 only when there is no usable answer.\n"
            "Return ONLY this JSON shape:\n"
            '{"question_score":0}\n\n'
            f"CV summary:\n{cv_summary}\n\n"
            f"Interview excerpts:\n{history_text}"
        )
    else:
        system = (
            "Tu es un interviewer technique senior. "
            "Evalue le candidat uniquement a partir des extraits d'entretien et du resume CV. "
            "Reponds UNIQUEMENT avec un objet JSON valide."
        )
        user = (
            "Retourne la note moyenne d'examen de 0 a 5 pour les reponses du candidat.\n"
            "Utilise 0 uniquement s'il n'existe aucune reponse exploitable.\n"
            "Le score 5 doit rester rare et justifie par des indices clairs, coherents et repetes.\n"
            "N'attribue pas 5 par defaut.\n"
            "Retourne UNIQUEMENT ce JSON :\n"
            '{"question_score":0}\n\n'
            f"Resume CV:\n{cv_summary}\n\n"
            f"Extraits d'entretien:\n{history_text}"
        )

    parsed = request_json(
        messages=build_chat_messages(
            system_content=system,
            user_content=user,
        ),
        max_tokens=180,
        temperature=0.1,
        log_mode="infer_scores_prompt_json",
        phase="FINAL",
    )
    normalized = normalize_scores(parsed)
    if _has_meaningful_scores(normalized):
        return normalized

    retry = request_json(
        messages=build_chat_messages(
            system_content=system,
            user_content=(
                f"{user}\n\n"
                "La reponse precedente a retourne des scores tous a 0. "
                "Recommence avec une reevaluation plus genereuse des qu'il existe un exemple concret, "
                "un raisonnement technique, une decision d'architecture, une optimisation ou un diagnostic."
            ),
        ),
        max_tokens=220,
        temperature=0.05,
        log_mode="infer_scores_prompt_json_retry",
        phase="FINAL",
    )
    normalized_retry = normalize_scores(retry)
    if _has_meaningful_scores(normalized_retry):
        return normalized_retry

    return _heuristic_competency_scores(history_text)
