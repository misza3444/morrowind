# Zależności i zasoby

Łowca Echa powstaje jako projekt niekomercyjny. Gotowe paczki wykorzystujemy zgodnie z ich licencjami; pochodzenie i zastosowanie wybranych modeli opisuje [ART_ASSETS.md](docs/ART_ASSETS.md).

**OpenMW 0.51.0** — silnik i narzędzia projektu OpenMW, GPLv3. Źródła wydania: <https://github.com/OpenMW/openmw/tree/openmw-0.51.0>. Lokalna paczka zawiera `LICENSE.txt`, listę pakietów oraz informacje o licencjach bibliotek i fontów. Projekt nie modyfikuje kodu silnika.

**OpenMW Example Suite**, commit `a41b44d9403ff3f8a1505c1b4bc152c4dd623b64` — <https://gitlab.com/OpenMW/example-suite>. Wykorzystywane są `game_template/data`, `example_animated_creature/data` oraz wybrane modele i tekstury z `the_hub/data` i `example_static_props/data`. Zgodnie z plikiem `LICENSE` zasoby są CC0 1.0, a konfiguracja MyGUI GPLv3. Pełne `LICENSE` i `AUTHORS.md` są zachowywane przy pobranej kopii w `.runtime/example-suite/` oraz w `licenses/` paczki Windows. Wybrane dodatkowe pliki i ich sumy kontrolne rejestruje `assets/manifest.json`. Informacje o bibliotekach i fontach zachowujemy z paczki OpenMW.

Autorzy Example Suite wymienieni przez upstream: Bret Curtis (psi29a), DestinedToDie, Isak Larborn, Leja Pelc (Mclawliet), Matjaž Lamut (Lamoot), Nelsson Huotari (unelsson). Pełna lista, w tym przypisania poszczególnych zasobów, pozostaje w upstream `AUTHORS.md`.

Paczka Windows zachowuje informacje licencyjne i oryginalny instalator Microsoft Visual C++ Redistributable dołączony przez OpenMW w `engine/redist/`. Jego niezmienione biblioteki x64 są rozmieszczane lokalnie przy silniku; ich pochodzenie i SHA-256 rejestruje `engine/app-local-runtime.json`. Nie są pobierane z nieoficjalnych serwisów DLL ani instalowane globalnie. Źródło natywnego launchera projektu znajduje się w `packaging/windows/launcher.c`.

Bootstrap i aktualizator są kodem tego projektu: `packaging/windows/bootstrap.c`, `UpdateCore.cs` i `Updater.cs`. Aktualizator korzysta z systemowego .NET Framework 4.8; paczka nie zawiera jego instalatora ani kopii środowiska .NET. Mono i Wine Mono użyte w środowisku deweloperskim służą do weryfikacji i nie są rozprowadzane w grze.

Układ areny, prosta geometria podłoża, ścian i znaków, zastępcze tekstury HUD i postaci oraz kod `game/scripts/echo` powstały w tym projekcie. Generowane pliki odtwarza `tools/build_content.py`; modele i tekstury zewnętrzne są kopiowane bez zmian na podstawie manifestu. Nie pobrano zasobów Bethesdy ani Solo Leveling. Nie należy traktować tego dokumentu jako nadania jednej licencji wszystkim przyszłym zasobom projektu.
