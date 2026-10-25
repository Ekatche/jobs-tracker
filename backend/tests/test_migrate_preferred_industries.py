from scripts.migrate_preferred_industries import migrate_industry_values


def test_migrate_industry_values():
    values = ["Finance", "Tech", "finance_insurance", "Aéronautique", "Tourisme", "Cuisine moléculaire"]

    migrated, unmatched = migrate_industry_values(values)

    # Doublon retiré, ordre conservé, "other" jamais produit
    assert migrated == ["finance_insurance", "tech_it", "industry_aerospace", "Tourisme", "Cuisine moléculaire"]
    assert unmatched == ["Tourisme", "Cuisine moléculaire"]
