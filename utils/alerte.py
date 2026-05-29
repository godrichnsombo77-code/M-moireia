CLASSES = {
    0: "Non-Violence",
    1: "Violence",
    2: "Arme a feu",
    3: "Couteau",
    4: "Personne",
}

NIVEAUX = {
    "INFO": 0,
    "MODERE": 1,
    "ELEVE": 2,
    "CRITIQUE": 3,
    "URGENCE": 4,
}

REGLES_ALERTE = [
    ({1, 2, 4}, "URGENCE", "Urgence absolue : violence armee sur une personne"),
    ({1, 3, 4}, "URGENCE", "Urgence absolue : agression au couteau sur une personne"),
    ({2, 3, 4}, "URGENCE", "Urgence absolue : personne avec plusieurs armes"),
    ({1, 2}, "CRITIQUE", "Danger immediat : violence avec arme a feu"),
    ({1, 3}, "CRITIQUE", "Danger immediat : violence avec couteau"),
    ({1, 4}, "CRITIQUE", "Agression detectee : violence sur une personne"),
    ({2, 4}, "CRITIQUE", "Danger : personne armee avec arme a feu"),
    ({3, 4}, "CRITIQUE", "Danger : personne armee avec couteau"),
    ({2, 3}, "CRITIQUE", "Alerte maximum : plusieurs armes detectees"),
    ({2}, "ELEVE", "Alerte : arme a feu detectee"),
    ({3}, "ELEVE", "Alerte : couteau detecte"),
    ({1}, "ELEVE", "Alerte : violence detectee"),
    ({4}, "MODERE", "Personne detectee, surveillance active"),
]


def get_class_names(class_ids: list[int]) -> list[str]:
    return [CLASSES.get(int(class_id), f"Classe {class_id}") for class_id in class_ids]


def get_alerte(classes_detectees: list[int]) -> dict:
    classes_set = {int(item) for item in classes_detectees}
    classes_set.discard(0)

    if not classes_set:
        return {
            "niveau": "INFO",
            "message": "Situation normale : aucune menace detectee",
            "priorite": 0,
            "classes_detectees": [],
        }

    for classes_requises, niveau, message in REGLES_ALERTE:
        if classes_requises.issubset(classes_set):
            return {
                "niveau": niveau,
                "message": message,
                "priorite": NIVEAUX[niveau],
                "classes_detectees": get_class_names(sorted(classes_set)),
            }

    return {
        "niveau": "INFO",
        "message": f"Elements detectes : {', '.join(get_class_names(sorted(classes_set)))}",
        "priorite": 0,
        "classes_detectees": get_class_names(sorted(classes_set)),
    }


def envoyer_alerte(alerte: dict) -> dict:
    if alerte.get("priorite", 0) >= 2:
        print(f"[ALERTE] {alerte.get('message', '')}")
    return alerte
