# Własne RPG akcji na OpenMW — rozeznanie

Stan sprawdzenia: 21 października 2026 r. Kierunek: autorska gra inspirowana dynamiką i rozwojem bohatera z *Solo Leveling: ARISE*. Silnik: OpenMW, zgodnie z decyzją użytkownika. Robocze założenie dla prototypu: PC, klawiatura i mysz, jeden gracz, offline.

**Wniosek:** OpenMW jest realną bazą samodzielnego RPG z lochami, umiejętnościami i przywołańcami. Największą niewiadomą jest jakość dynamicznej walki: combo, przerywanie animacji i szybki unik z kolizjami. Najpierw trzeba sprawdzić te elementy na jednej arenie. Istnienie API nie dowodzi jeszcze, że osiągniemy responsywność ARISE bez zmian C++.

**Podstawa techniczna i zakres sprawdzenia**

Sprawdzono oficjalne wydanie [OpenMW 0.51.0][release], oznaczone przez GitHub jako „Latest”, opublikowane 19 czerwca 2026 r. Analiza kodu i dokumentacji dotyczy tagu `openmw-0.51.0`, commit `f4bec41444214a7903bebd178389ca22ca13f646`, a nie bieżącego `master`.

Przejrzano również oficjalny [Example Suite / Game Template][template-repo] w commicie `a41b44d9403ff3f8a1505c1b4bc152c4dd623b64` i [eksporter COLLADA][exporter] w commicie `c4134defa0b4377bc382738b5580a12573e0a8c8`. Ich dokumentacja pomaga ustalić ścieżkę startu; zgodność całego zestawu z 0.51.0 wymaga uruchomienia.

To badanie źródeł, nie walidacja gry. Nie kompilowano ani nie uruchamiano silnika, nie testowano importu modeli, zachowania walki ani wydajności. Oficjalna witryna ARISE oraz serwisy openmw.org i Read the Docs były niedostępne przez obecną politykę sieciową; dokumentację OpenMW odczytano z oficjalnego repozytorium. Zakres inspiracji ARISE jest propozycją projektową, nie audytem aktualnej zawartości tej gry.

**Samodzielna gra, bez danych Morrowinda**

OpenMW jest otwartą implementacją silnika, a nie udostępnionym kodem źródłowym Bethesdy. Oficjalny [Game Template][template-doc] zawiera podstawowe zasoby i `template.omwgame`, pozwalające zacząć własną grę bez `Morrowind.esm` i archiwów BSA. W obecnym Example Suite szablon znajduje się w `game_template/`; nie należy bez sprawdzenia kopiować starych ścieżek z instrukcji.

Proponowana baza projektu to własny plik `.omwgame`, osobne katalogi zasobów, skrypty rejestrowane w `.omwscripts` i konfiguracja uruchomienia niezależna od instalacji Morrowinda. OpenMW-CS posłuży do rekordów i poziomów. Modele, świat, interfejs i nazwy będą autorskie.

**Co silnik daje, a co trzeba zbudować**

| Element docelowej gry | Potwierdzona podstawa w OpenMW 0.51.0 | Praca i ograniczenia |
| --- | --- | --- |
| Kamera zza pleców i wybór celu | `openmw.camera`: pozycja, kąty, dystans, przesunięcie punktu kadrowania, FOV; lista pobliskich aktorów | Własny wybór i zmiana celu, wygładzanie, sprawdzanie widoczności i zachowanie przy ścianach. |
| Bezpośrednie sterowanie | `Controls.overrideMovementControls`, `overrideCombatControls`, `self.controls` | Można przejąć wejście, ale nie oznacza to pełnego zastąpienia kontrolera postaci. |
| Combo i moment zadania obrażeń | API animacji, text keys, `AnimationController`, zdarzenie końca animacji | Własna maszyna stanów, bufor wejścia, okna trafień i reguły przerywania. Kontroler C++ może zmieniać lub anulować animacje. |
| Trafienia zależne od zasięgu | `nearby.castRay`, także z promieniem sfery; zdarzenie `Hit`, interfejs `Combat` | Własne sprawdzanie kierunku/zasięgu i jednokrotne naliczanie obrażeń na cel na cios. Pojedynczy raycast nie daje pełnego śledzenia ostrza. |
| Unik i krótka nietykalność | Przejęcie ruchu i obsługi trafień | Należy sprawdzić ruch z kolizjami, schody i granice areny. Teleportowanie co klatkę nie będzie podstawą uniku. |
| Umiejętności i cooldowny | Lua, VFX, statystyki, tworzenie rekordów; 0.51 dodaje własne efekty magiczne | Własne koszty, cooldowny, animacje i reguły efektów. Dostępność funkcji zależy od kontekstu skryptu. |
| Przywoływany wojownik | Tworzenie obiektów, pakiety AI `Follow` i `Combat` | Własne wybieranie celu, czas istnienia, limit przywołań i reakcja na zmianę lokacji. |
| Krótkie wyprawy do lochów | Komórki świata, przenoszenie obiektów, skrypty globalne | Pierwszy loch ręcznie zbudowany. Powtarzalny start, reset wrogów i nagród wymagają własnej logiki. |
| Boss z czytelnymi atakami | Sterowanie aktorem, animacje, VFX, AI | Własne fazy, sygnalizowanie ataków, przerwy i warunki zwycięstwa. |
| HUD, rozwój i zapis | `openmw.ui`, statystyki, `onSave` / `onLoad` | Własny pasek umiejętności, postęp, dane nagród i wersjonowanie zapisu. |

Podstawy powyższej tabeli: [kamera][camera], [sterowanie][controls], [animacje][animation], [kontroler animacji][animation-controller], [kolizje][nearby], [Combat][combat], [zdarzenia][events], [świat][world], [konteksty Lua][lua].

**Najważniejsze ryzyka techniczne**

1. **Animacje i kontroler postaci.** Dokumentacja `playBlended` wprost ostrzega, że kontroler zakodowany w C++ może zmienić lub anulować animację, i wskazuje `playQueued` jako ścieżkę skryptową. Trzeba sprawdzić zgodność kolejkowania, blendowania, ruchu i przerywania ataków. Jeżeli Lua nie wystarczy, dopiero wynik tej próby określi potrzebną zmianę C++.
2. **Mechanika obrażeń.** Bazowy `Combat` zawiera również funkcje będące pustymi implementacjami; część zasad Morrowinda jest dostarczana osobno w `files/data-mw/scripts/omw/combat/`. Samo wysłanie `Hit` nie jest dowodem działającej własnej walki. Prototyp musi potwierdzić faktyczny spadek HP, pomijanie obrażeń podczas uniku, śmierć i brak podwójnego trafienia. Prywatne API z prefiksem `_` nie powinno stanowić stabilnego kontraktu naszej gry.
3. **Import postaci.** Oficjalna [ścieżka Blender → COLLADA][model-pipeline] obejmuje animowane modele, text keys i root `Bip01`. Tutorial dotyczy stworzenia; nie dowodzi automatycznie zgodności dowolnego riga gracza. Dokumentacja podaje jako ostatnią potwierdzoną wersję Blender 3.0, więc nowszy Blender i eksporter trzeba sprawdzić, zanim powstaną docelowe postacie. [Przegląd formatów][models] opisuje ich pozostałe ograniczenia.
4. **Wygląd.** [Dokumentacja materiałów][materials] tej ścieżki opisuje materiały specular, nie standardowy workflow PBR. Cel: czytelna, stylizowana grafika, mocne sylwetki i efekty zdolności. Nie zakładamy automatycznego importu gotowego pakietu GLB/FBX ani wyglądu ARISE po wgraniu modeli.
5. **Opóźnienia i zapis.** Skrypty lokalne/globalne mają różne uprawnienia, a zdarzenia są przekazywane między kontekstami. Trzeba sprawdzić synchronizację animacji z obrażeniami oraz zachowanie cooldownów i przywołań po wczytaniu.

**Proponowana architektura**

- Skrypty gracza: wejście, kamera, wybór celu, combo, unik i HUD.
- Skrypty lokalne aktorów: reakcja na trafienie, nietykalność, animacje, zachowanie przeciwników i przywołańców.
- Skrypty globalne: stan wyprawy, tworzenie i usuwanie obiektów, nagrody oraz trwały postęp. Przepływ danych ma respektować uprawnienia poszczególnych kontekstów Lua.
- Dane treści: arena, rekordy postaci i wrogów, modele, animacje, dźwięki oraz efekty.
- Silnik: początkowo niezmieniony OpenMW 0.51.0. Ewentualne poprawki C++ dopiero po wskazaniu konkretnej przeszkody w prototypie.

Gdyby potrzebne były zmiany silnika, sprawdzony kod 0.51.0 używa C++20 i CMake; zależności obejmują m.in. OpenSceneGraph, Bullet w podwójnej precyzji, SDL2, LuaJIT, MyGUI oraz Qt6 dla narzędzi. To osobny etap przygotowania i utrzymywania kompilacji, nie drobna zmiana skryptu.

**Pierwsza grywalna wersja**

Proponuję zachować roboczy pomysł „Łowcy Echa”: bohater zdobywa echa pokonanych stworzeń i używa ich mocy podczas kolejnych wypraw. Pierwsza wersja ma sprawdzać walkę i poczucie wzrostu siły.

- Jedna postać, jedna broń i kamera zza pleców z opcjonalnym namierzaniem.
- Combo z trzech ciosów, unik z krótkim oknem nietykalności i dwie umiejętności.
- Jeden podstawowy przeciwnik oraz boss z dwoma czytelnymi atakami.
- Jedna arena i wyprawa na około 5–10 minut; po zwycięstwie jedna nagroda i możliwość powtórzenia.
- Jeden przywołaniec dodany po sprawdzeniu podstawowej walki.
- Własne zasoby zastępcze, HUD HP i cooldownów. Multiplayer, duży świat, rozbudowana drużyna i system gacha pozostają poza zakresem tego prototypu.

**Kolejność prac i warunki przejścia dalej**

| Etap | Wynik do sprawdzenia |
| --- | --- |
| 1. Samodzielna baza | Game Template uruchamia się w OpenMW 0.51.0 bez danych Morrowinda; działają ruch, kamera, zapis i ponowne wczytanie. |
| 2. Próba zasobów | Własny animowany model przechodzi eksport i import; idle, ruch oraz atak działają ze skalą, kolizją i poprawnym momentem trafienia. Osobno potwierdzamy rig gracza. |
| 3. Próba walki | Trzy ciosy można połączyć; bufor wejścia działa, trafienie obniża HP dokładnie raz na cios, a atak spoza zasięgu lub przez ścianę nie trafia. |
| 4. Próba uniku | Unik przerywa dozwolone stany, respektuje kolizje i okno nietykalności; sprawdzenie przy 30, 60 i 120 FPS nie wykazuje zależności zasad od liczby klatek. |
| 5. Pełna wyprawa | Boss, zdolności, nagroda, przegrana i restart tworzą kompletną pętlę; zapis/wczytanie nie powiela nagród ani przywołań. |

To plan walidacji, a nie lista wykonanych testów. Po etapie 3–4 można ocenić, czy wystarczy Lua, czy potrzebujemy zmian C++. Dopiero wtedy warto zwiększać liczbę lokacji i inwestować w docelowe animacje. Cel 60 FPS ustalimy dla konkretnego sprzętu; na tym etapie nie ma pomiarów ani podstaw do estymacji terminu całej gry.

**Licencje i dystrybucja**

OpenMW jest na [GPLv3][license]. Dystrybucja własnej zmodyfikowanej wersji silnika wymaga spełnienia obowiązków tej licencji, w tym dotyczących odpowiadającego kodu źródłowego. Zasoby gry wymagają własnej ewidencji licencji; nie należy automatycznie przenosić na nie zasad licencjonowania silnika ani zakładać statusu całego pakietu.

Obecny [LICENSE Example Suite][template-license] rozróżnia zasoby CC0 i konfigurację MyGUI na GPLv3. Starsza instrukcja dodatkowo wyróżnia font Pelagiad. Przy wyborze faktycznie kopiowanych plików trzeba zachować ich informacje o autorach i sprawdzić licencje, szczególnie fontów. Postacie, nazwy, grafika i muzyka z Solo Leveling nie są materiałem wejściowym do naszej gry.

**Stan w chwili zakończenia rozeznania, przed implementacją:** dodano ten dokument; kod gry i konfiguracja nie były jeszcze utworzone. Późniejszy stan prototypu opisują [README](../README.md) oraz [walidacja](VALIDATION.md). Kopie źródeł użyte wyłącznie do analizy nie są zależnościami gry.

[release]: https://github.com/OpenMW/openmw/releases/tag/openmw-0.51.0
[template-repo]: https://gitlab.com/OpenMW/example-suite/-/tree/a41b44d9403ff3f8a1505c1b4bc152c4dd623b64
[template-doc]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/modding/openmw-game-template.rst
[exporter]: https://github.com/OpenMW/collada-exporter/tree/c4134defa0b4377bc382738b5580a12573e0a8c8
[camera]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/lua_api/openmw/camera.lua
[controls]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/data/scripts/omw/input/playercontrols.lua
[animation]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/lua_api/openmw/animation.lua
[animation-controller]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/data/scripts/omw/mechanics/animationcontroller.lua
[nearby]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/lua_api/openmw/nearby.lua
[combat]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/data/scripts/omw/combat/interface.lua
[events]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/lua-scripting/events.rst
[world]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/files/lua_api/openmw/world.lua
[lua]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/lua-scripting/overview.rst
[models]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/modding/custom-models/index.rst
[model-pipeline]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/modding/custom-models/pipeline-blender-collada-animated-creature.rst
[materials]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/docs/source/reference/modding/custom-models/pipeline-blender-collada-static-models.rst
[license]: https://github.com/OpenMW/openmw/blob/openmw-0.51.0/LICENSE
[template-license]: https://gitlab.com/OpenMW/example-suite/-/blob/a41b44d9403ff3f8a1505c1b4bc152c4dd623b64/LICENSE
