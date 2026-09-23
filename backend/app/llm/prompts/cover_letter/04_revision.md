Tu dois réviser une lettre de motivation existante.

Tu disposes de :

1. la lettre originale ;
2. le JSON d'analyse factuelle ;
3. les défauts identifiés par le critique ;
4. les violations des garde-fous déterministes.

Ton objectif est d'améliorer uniquement les éléments qui posent réellement problème.

{voice_style_block}

## Principe de révision minimale

Conserve autant que possible :

* le ton ;
* le vocabulaire ;
* les idées ;
* le niveau de précision ;
* la personnalité de la lettre.

Ne réécris pas toute la lettre lorsqu'une seule phrase doit être corrigée.

EXCEPTION DE RESTRUCTURATION : Si le critique signale un « CV déguisé (Catalogue) », ou si les garde-fous relèvent une ouverture d'employeur interdite, le principe de révision minimale NE S'APPLIQUE PAS à la structure. Tu dois alors réorganiser entièrement les paragraphes autour du fil rouge (synthèse thématique) du JSON, en supprimant toute énumération chronologique ou par employeur, et en construisant une véritable argumentation transverse.


## Premier paragraphe

Si le critique signale le premier paragraphe, réécris uniquement ce paragraphe.

Il doit faire 2 à 3 phrases, à la première personne, sur un ton factuel : ce que le candidat fait, un point concret de son travail présent dans le JSON qui rejoint le poste, et pourquoi ce poste l'intéresse en citant un élément concret de l'offre.

Supprime toute phrase générale sans « je », toute maxime et tout vocabulaire solennel : « conviction », « enjeu », « au cœur de », « exige avant tout », « véritable », « crucial », « passionné », « défi ».

Ne rends jamais ce paragraphe plus sophistiqué qu'il ne l'était. En cas de doute, choisis la formulation la plus simple.

Ne transforme pas ce paragraphe en présentation de l'entreprise.

## Transitions

Si une transition est jugée abrupte, modifie prioritairement la première phrase du paragraphe concerné.

La nouvelle phrase doit prolonger naturellement l'idée du paragraphe précédent.

N'ajoute pas simplement :
« De plus »
« Par ailleurs »
« En outre »
« Enfin »

Une transition doit créer un lien d'idée, pas seulement un lien grammatical.

## Fluidité

Corrige les phrases :

* trop longues ;
* trop complexes ;
* répétitives ;
* artificiellement structurées.

Lorsque deux phrases courtes produisent un rythme haché, tu peux les fusionner.

Lorsque une phrase contient trop d'informations, tu peux la diviser.

Ne cherche pas à rendre toutes les phrases de longueur similaire.

## Naturel

Supprime les formulations qui semblent avoir été écrites pour impressionner plutôt que pour informer.

Privilégie une formulation simple lorsqu'elle exprime la même idée.

Ne remplace pas systématiquement les mots simples par des synonymes plus sophistiqués.

Ne rajoute pas de vocabulaire marketing.

## Faits

Le JSON d'analyse constitue la seule source de vérité factuelle.

N'ajoute :

* aucune expérience ;
* aucune technologie ;
* aucun chiffre ;
* aucun résultat ;
* aucune responsabilité ;
* aucune information sur l'entreprise

qui n'apparaisse dans les données fournies.

## Garde-fous

Respecte les violations déterministes signalées.

Supprime :

* les points d'exclamation ;
* les points de suspension ;
* les tirets cadratins ;
* les parenthèses ;
* les formulations interdites.

Conserve au maximum un point-virgule.

## Longueur

Conserve une longueur comprise entre {min_words} et {max_words} mots.

Si la lettre respecte déjà cette longueur, ne la raccourcis pas ou ne l'allonge pas artificiellement.

## Contexte

Lettre originale :
{letter_text}

JSON d'analyse factuelle :
{analyst_json}

Défauts identifiés par le critique :
{critic_flaws}

Violations des garde-fous déterministes :
{violations}

## Contrôle final

Avant de retourner la lettre, vérifie silencieusement :

1. Chaque correction répond-elle à un défaut réellement signalé ?
2. Ai-je conservé la voix originale et le style personnel demandé ?
3. Ai-je introduit une information absente du JSON ?
4. Les paragraphes s'enchaînent-ils naturellement ?
5. Le premier paragraphe est-il simple, à la première personne et spécifique au poste ?
6. La lettre reste-t-elle naturelle lorsqu'elle est lue à voix haute ?
7. Ai-je ajouté des formulations génériques pour remplir la longueur ?

Si une modification n'améliore aucun de ces points, ne la fais pas.

Retourne uniquement la lettre finale.
