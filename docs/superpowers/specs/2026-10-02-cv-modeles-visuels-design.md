# Modèles visuels du CV adapté : Classique, Créatif, couleur d'accent, garanties ATS

Date : 2026-10-02

Sous-projet B du CV multi-métiers
(`2026-09-29-cv-multi-metiers-design.md:41`). Le sous-projet A (textes
neutres, données candidat étendues) est livré.

## Contexte

Le CV adapté propose deux modèles, `sidebar_elegance` et
`executive_minimalist`, pensés pour des profils tech. Ils ne conviennent ni
à un profil opérationnel ou RH, qui attend un CV sobre, ni à un profil
marketing ou communication, qui attend un CV plus visuel. La couleur est
fixée à un bleu marine.

Le rendu passe par du HTML Jinja2 (`render_cv_html`,
`backend/app/services/cv_templates.py`), puis par un PDF A4 vectoriel produit
par Chromium (`cv_pdf_renderer.py`). Le but premier du CV est de **passer les
filtres ATS** : un ATS lit le texte extrait du PDF, pas son rendu. Or les
modèles actuels ont plusieurs défauts d'extraction :

- Sidebar Elegance place la colonne latérale en premier dans le HTML. Son
  monogramme (« TL ») est du texte réel, extrait avant le nom.
- Les contacts sont précédés d'emojis (✉ ☎ 📍 🔗 💻 🌐), qui produisent des
  glyphes parasites à l'extraction.
- Les compétences en badges n'ont aucun séparateur textuel entre elles :
  « PythonFastAPI » à l'extraction.
- Les ligatures d'Inter (« fi », « fl ») sont extraites comme un seul
  caractère spécial.
- Les titres de section ne sont pas uniformes (« Expérience Professionnelle »,
  « Projets Clés & Réalisations »).

La liste des modèles est écrite en dur à cinq endroits :

- `cv_templates.py:47` ;
- `ResumePreviewModal.tsx:209` et `ResumePreviewModal.tsx:241-266` ;
- `app/resumes/page.tsx:405-429` ;
- `ResumeCard.tsx:87` ;
- `models.py:751` (commentaire).

L'API ne valide pas le nom du modèle.

## Objectifs

- Deux nouveaux modèles :
  - **Classique**, pour la logistique, l'industrie et les RH ;
  - **Créatif**, pour le marketing et la communication.
- Une **couleur d'accent** choisie par l'utilisateur, valable pour les quatre
  modèles. Elle se choisit à la génération et peut être changée dans l'aperçu
  sans régénérer le CV.
- La **modernisation** des deux modèles existants.
- Des **garanties ATS** vérifiées par un test qui rend un vrai PDF pour chacun
  des quatre modèles.
- Une seule source de vérité pour la liste des modèles et des couleurs.

## Non-objectifs

- **Optimisation ATS du contenu** : reprise des termes exacts de l'offre,
  sigles accompagnés de leur forme longue, score de couverture des mots-clés
  dans l'aperçu. Ce sera le sous-projet C, avec son propre spec, après la
  livraison de celui-ci.
- Une recommandation automatique du modèle selon l'offre : le choix reste
  manuel.
- Une couleur libre (sélecteur de couleur, code hexadécimal saisi par
  l'utilisateur).
- Tout changement de `TailoredCVSchema` ou du prompt d'adaptation.
- Une migration de base de données.
- La répétition de la colonne latérale de Sidebar Elegance sur la page 2.

## Design

### 1. Garanties ATS

Chaque modèle respecte les règles suivantes. Chacune est vérifiée par le test
PDF de la section 6.

1. **Le nom est la première ligne extraite.**
   - Dans le HTML, le contenu principal précède toute colonne latérale. Le
     placement visuel passe par la grille CSS (`grid-template-areas`).
2. **Les colonnes ne s'entrelacent pas.** Les lignes d'un poste et de ses
   puces sont extraites d'un seul bloc, sans ligne de la colonne latérale au
   milieu.
3. **Les titres de section sont standard**, tirés d'une source unique :
   - Expérience professionnelle ;
   - Compétences ;
   - Formation ;
   - Langues ;
   - Certifications & habilitations ;
   - Projets ;
   - Centres d'intérêt.
4. **Les compétences sont séparées dans le texte.** Entre deux pastilles se
   trouve un « · » visible et discret (classe `.dot`, couleur
   `--accent-line`).
   - Essai du 2026-10-02 (Chromium, pdfplumber et pymupdf) : un séparateur
     invisible n'est pas restitué. Les techniques `sr-only` (zone découpée),
     texte transparent et largeur nulle le perdent ou le déplacent. Un texte
     blanc de 1 px passe, mais c'est du texte caché, que certains ATS
     pénalisent. Seul le « · » visible est extrait correctement
     (« Python · FastAPI »).
5. **Le PDF ne contient aucun emoji.** Les icônes sont des SVG au trait
   (chemins, aucun `<text>`). Chaque contact reste écrit en texte réel.
6. **Les ligatures sont désactivées** : `font-variant-ligatures: none` sur
   `body`.
7. **Les contacts sont dans le corps de la page**, jamais dans l'en-tête ou
   le pied de page PDF. Le PDF ne contient aucun texte rendu en image.
8. **Le monogramme n'est pas du texte.** Les initiales sont dessinées dans un
   `<canvas>` par un court script, en résolution 4× pour l'impression. Le
   canvas est intégré au PDF comme une image. Le moteur de rendu exécute déjà
   le JS de la page (`cv_pdf_renderer.py:26`, `set_content`).
   - Toute lettre visible écrite en HTML, en SVG `<text>` ou en CSS `content:`
     resterait extraite. Un ATS qui lit par position lirait alors « TL » sur
     la ligne du nom.

### 2. Registre et API

**Registre**, dans `backend/app/services/cv_templates.py` :

```python
CV_TEMPLATES = ("sidebar_elegance", "executive_minimalist", "classique", "creatif")
CV_TEMPLATES_WITHOUT_PHOTO = frozenset({"classique"})
CV_ACCENTS = {
    "marine":    {"primary": "#1e3a8a", "tint": "#eef2fb", "line": "#a9b8e0"},
    "bleu_vert": {"primary": "#0f766e", "tint": "#e6f2f1", "line": "#99c9c4"},
    "ardoise":   {"primary": "#4f6d8a", "tint": "#eff3f7", "line": "#b3c3d3"},
    "sauge":     {"primary": "#4d6b4f", "tint": "#eff4ef", "line": "#b5c7b6"},
    "bordeaux":  {"primary": "#8b1e3f", "tint": "#f8eef1", "line": "#d8a9b7"},
    "graphite":  {"primary": "#374151", "tint": "#f1f2f4", "line": "#c3c7ce"},
}
DEFAULT_TEMPLATE = "sidebar_elegance"
DEFAULT_ACCENT = "marine"
```

Marine est la couleur actuelle des CV : un ancien document garde donc son
apparence.

**Rendu** : `render_cv_html(..., accent: str = DEFAULT_ACCENT)`.

- Le modèle est validé contre `CV_TEMPLATES`. La liste écrite en dur à la
  ligne 47 disparaît.
- La fonction injecte en tête du CSS un bloc `:root` qui définit `--accent`,
  `--accent-tint` et `--accent-line`. Les valeurs viennent toujours de
  `CV_ACCENTS` et jamais d'une saisie utilisateur.
- Pour un modèle de `CV_TEMPLATES_WITHOUT_PHOTO`, `with_photo` est forcé à
  `False`.
- Une clé de modèle ou de couleur inconnue (ancien document, valeur
  corrompue) bascule sur la valeur par défaut, avec un log `warning`. C'est le
  comportement actuel pour le modèle.

**Données** : `TailoredResumeInDB.accent: str = "marine"`. Les documents
existants n'ont pas ce champ et reçoivent marine. Aucune migration n'est
nécessaire. Le commentaire de `models.py:751` est supprimé.

**API** (`backend/app/routers/resumes.py`) :

- `GenerateResumeRequest` : `template` et `accent` sont typés par des
  `Literal` construits à partir du registre, avec `DEFAULT_TEMPLATE` et
  `DEFAULT_ACCENT` comme valeurs par défaut. Une valeur hors registre renvoie
  une 422.
- `UpdateResumeRequest` : `template` et `accent` sont optionnels et validés de
  la même façon.
- `GET /resumes/{id}/pdf` accepte un paramètre d'URL `accent`, à côté de
  `template` et `with_photo`. Ces trois paramètres sont validés et une valeur
  invalide renvoie une 422.
  - Sans paramètre, le point d'accès utilise la valeur enregistrée sur le
    document, ou la valeur par défaut si le document n'en a pas.

### 3. Frontend

**Constante miroir** : `frontend/src/lib/cvTemplates.ts`.

```ts
export const CV_TEMPLATES = [
  { key: "sidebar_elegance", label: "Sidebar Elegance",
    hint: "2 colonnes · tech, data, profils riches en compétences", supportsPhoto: true },
  { key: "executive_minimalist", label: "Executive Minimalist",
    hint: "1 colonne épurée · cadres, conseil, finance", supportsPhoto: true },
  { key: "classique", label: "Classique",
    hint: "Sobre, sans photo · logistique, industrie, RH", supportsPhoto: false },
  { key: "creatif", label: "Créatif",
    hint: "En-tête en carte, photo possible · marketing, communication", supportsPhoto: true },
] as const;
export const CV_ACCENTS = [
  { key: "marine", label: "Marine", primary: "#1e3a8a" },
  // bleu_vert, ardoise, sauge, bordeaux, graphite : mêmes valeurs que le backend
] as const;
export type CvTemplateKey = (typeof CV_TEMPLATES)[number]["key"];
export type CvAccentKey = (typeof CV_ACCENTS)[number]["key"];
```

- **Types** : `types/resume.ts` utilise `CvTemplateKey` et ajoute
  `accent: CvAccentKey` à `TailoredResume`, ainsi qu'aux requêtes de
  génération et de mise à jour.
- **Client API** (`lib/api.ts`) : `generate`, `update`, `getPdfBlobUrl` et
  `downloadPdf` acceptent `accent`.
- **`ResumeCard.tsx`** : le libellé du modèle vient de la constante, et le
  téléchargement transmet `resume.accent`.

**Fenêtre « Générer mon CV »** (`app/resumes/page.tsx`) :

- Quatre cartes de modèle en grille 2×2, chacune avec son libellé et sa
  ligne d'aide.
- En dessous, une rangée « Couleur » de six pastilles rondes, marine
  sélectionnée par défaut.
  - Chaque pastille est un `<button type="button">` avec `aria-label` (le nom
    de la couleur), `aria-pressed` et `title`.
- `accent` est envoyé avec la requête de génération.

**Aperçu** (`ResumePreviewModal.tsx`) :

- Une seconde barre d'outils sous l'en-tête porte trois réglages :
  - Modèle : quatre boutons segmentés ;
  - Couleur : six pastilles ;
  - Photo.
- Changer de couleur suit le même chemin qu'un changement de modèle : `PUT`,
  puis rechargement du PDF. Le LLM n'est pas rappelé.
  - Le callback `onUpdateTemplate` devient
    `onUpdateAppearance(id, { template, accent, withPhoto })`.
- Le bouton Photo est masqué quand le modèle ne gère pas la photo
  (`supportsPhoto: false`). L'état `withPhoto` est conservé : la photo
  revient quand on repasse à un autre modèle.
- **Garde contre les réponses dans le désordre** : un compteur `useRef`
  numérote chaque chargement de PDF. Une réponse dont le numéro n'est pas le
  dernier est ignorée, et son URL blob est révoquée.
- Le sous-titre « Modèle X » lit son libellé dans la constante.

### 4. Modèles HTML/CSS

**Parties communes** :

- `backend/app/templates/cv/_macros.html` (Jinja) :
  - `section_titles` : la source unique des titres de la règle ATS 3 ;
  - `contacts(candidate)` : chaque contact affiche une icône SVG au trait
    (e-mail, téléphone, lieu, LinkedIn, GitHub, site, mobilité,
    disponibilité), suivie du texte réel ;
  - `chips(skills)` : les pastilles, séparées par le « · » de la règle ATS 4 ;
  - `tools_line(techs)` : les outils sous chaque poste, sous la forme
    « A · B » ;
  - `monogram(initials)` : le `<canvas>` et son script de dessin.
- `base_cv.css` :
  - `--color-primary` et `--color-primary-light` deviennent des alias de
    `--accent` et `--accent-tint` ;
  - ajout de `font-variant-ligatures: none` sur `body` ;
  - `.chip`, `.dot` et `.icon` remplacent `.badge` et `.badge-primary` ;
  - `.monogram` passe d'un dégradé à un fond uni `--accent`.
- Chaque modèle garde dans son fichier le CSS de sa propre mise en page.

**Modernisation commune aux deux modèles existants** :

- icônes SVG à la place des emojis ;
- pastilles fines à la place des badges gris ;
- outils en texte « A · B » sous chaque poste ;
- suppression du trait noir de 2 px et du cadre gris de l'accroche ;
- nom plus grand, avec un interlettrage resserré ;
- titres de section en majuscules (`text-transform: uppercase`), en petite
  taille, avec un interlettrage de `.08em` au plus, dans la couleur d'accent.
  - Pas de `font-variant: small-caps` : l'essai du 2026-10-02 montre que
    Chromium casse alors l'extraction (« C ' / ENTRES D INTÉRÊT »). Un
    interlettrage plus large risque de séparer les lettres à l'extraction.
  - Le HTML garde la casse normale (« Expérience professionnelle ») ; seul le
    CSS met en majuscules. Les tests d'extraction comparent sans tenir compte
    de la casse.

**Les quatre modèles** :

| Modèle | Ordre dans le HTML | Mise en page |
|---|---|---|
| `sidebar_elegance` | `<main>` (en-tête, accroche, expériences, projets), puis `<aside>` | `grid-template-areas` place `aside` à gauche. Colonne en teinte `--accent-tint`. Photo ou monogramme canvas sur fond `--accent`. La colonne latérale contient les contacts, les compétences, la formation, les langues, les certifications et les intérêts. |
| `executive_minimalist` | une colonne | En-tête, accroche, expériences, compétences, certifications, projets. Le pied de page sur trois colonnes regroupe formation, langues et intérêts. |
| `classique` | une colonne | En-tête aligné à gauche, police sans empattement. Titres sur bandeau gris (`--color-slate-100`), dates alignées à droite. L'accent ne colore que le nom et le titre visé. Jamais de photo. |
| `creatif` | une colonne | Carte d'en-tête arrondie, teinte `--accent-tint`, avec photo ronde en option, nom, titre et contacts. Corps en une colonne. Titres marqués d'un point `--accent` et d'un filet `--accent-line`. Pastilles fines. Le bas de page sur trois colonnes regroupe formation, langues et intérêts. |

Les maquettes validées (fichiers éphémères, hors dépôt) sont dans
`.superpowers/brainstorm/78029-1790960830/content/` :

- `classique-layout.html` (choix B) ;
- `creatif-layout-v2.html` (choix B) ;
- `modernisation-existants.html`.

**Bas de page sur trois colonnes** (Minimalist et Créatif) : un ATS qui lit
par position peut mêler les lignes des trois colonnes. Le risque est accepté,
car chaque colonne ne contient que deux ou trois lignes courtes sous un titre
standard. Le test vérifie que, dans l'ordre du HTML, chaque titre est suivi de
son contenu.

**Pagination** : chaque poste garde la classe `.page-break-avoid`. Les
sections entières (Expérience, Projets) ne l'ont pas, pour pouvoir se couper
entre deux pages.

### 5. Gestion des erreurs

| Situation | Comportement |
|---|---|
| `template` ou `accent` hors registre dans une requête d'API | 422, avec le message standard de validation FastAPI |
| Document en base avec une clé inconnue ou absente | Repli sur la valeur par défaut, log `warning`, PDF rendu normalement |
| `with_photo=True` avec `classique` | Ignoré sans erreur, aucune photo |
| Script du canvas en échec | Monogramme vide, rien d'autre n'est touché |
| Échec du rendu PDF | Inchangé : 500 « Échec du rendu PDF du CV. » |

### 6. Tests

**`backend/tests/test_cv_templates.py`** (rendu HTML, sans Chromium) :

- les quatre modèles s'affichent avec un profil complet ;
- `accent="bordeaux"` injecte `--accent: #8b1e3f` ;
- une clé de modèle ou de couleur inconnue bascule sur la valeur par défaut ;
- `classique` avec `with_photo=True` ne produit aucune balise `<img>` ;
- aucun caractère des plages emoji n'apparaît dans le HTML ;
- dans `sidebar_elegance`, `<main>` précède `<aside>`.

**`backend/tests/test_resumes_api.py`** :

- génération et mise à jour avec un `accent` valide : 200, et la valeur est
  enregistrée ;
- `template` ou `accent` hors registre : 422 sur `POST`, `PUT` et
  `GET /pdf` ;
- un document sans champ `accent` donne un PDF rendu en marine.

**`backend/tests/test_cv_pdf_renderer.py`** : Chromium et `pdfplumber`,
paramétré sur les quatre modèles. Le profil de test est complet : au moins
trois postes, des listes de compétences longues, une certification contenant
« certifié », des intérêts, et assez de contenu pour occuper deux pages.

1. La première ligne non vide extraite est le nom.
2. Chaque titre de `section_titles` présent dans les données est extrait.
3. « Python · FastAPI » est extrait, jamais « PythonFastAPI ».
4. Les puces d'un poste suivent son intitulé, sans ligne de la colonne
   latérale entre elles. Ce contrôle lit l'ordre du flux avec `pymupdf`
   (`get_text(sort=False)`).
5. « certifié » est extrait tel quel, sans le caractère `ﬁ` (U+FB01).
6. Les initiales du monogramme n'apparaissent pas comme ligne isolée
   (`sidebar_elegance` sans photo).
7. Aucun caractère des plages emoji ni de la zone à usage privé n'est
   extrait.

**Frontend** : il n'y a pas de framework de test. La vérification passe par
`npm run lint` et `npm run build`, puis par une vérification à la main dans le
navigateur :

- l'aperçu des quatre modèles en deux couleurs ;
- le bouton Photo masqué pour Classique ;
- des clics rapides sur plusieurs couleurs : l'aperçu doit afficher la
  dernière couleur choisie ;
- un téléchargement depuis `ResumeCard`.

**Contrôle visuel** : un PDF par modèle, rendu sur un profil de démonstration
et relu à l'œil avant la livraison.

## Fichiers touchés

Backend :

- `backend/app/services/cv_templates.py`
- `backend/app/routers/resumes.py`
- `backend/app/models.py`
- `backend/app/templates/cv/base_cv.css`
- `backend/app/templates/cv/_macros.html` (nouveau)
- `backend/app/templates/cv/sidebar_elegance.html`
- `backend/app/templates/cv/executive_minimalist.html`
- `backend/app/templates/cv/classique.html` (nouveau)
- `backend/app/templates/cv/creatif.html` (nouveau)
- `backend/tests/test_cv_templates.py`
- `backend/tests/test_resumes_api.py`
- `backend/tests/test_cv_pdf_renderer.py`

Frontend :

- `frontend/src/lib/cvTemplates.ts` (nouveau)
- `frontend/src/types/resume.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/app/resumes/page.tsx`
- `frontend/src/components/resumes/ResumePreviewModal.tsx`
- `frontend/src/components/resumes/ResumeCard.tsx`

`backend/app/templates/cv/sidebar_elegance.html`, `backend/app/models.py` et
`frontend/src/lib/api.ts` contiennent déjà des modifications non commitées de
l'utilisateur. Le plan d'implémentation devra s'appuyer dessus sans les
écraser.
