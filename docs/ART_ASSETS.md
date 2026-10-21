# Modele i tekstury

Łowca Echa jest projektem niekomercyjnym. Korzystamy z gotowych paczek modeli, jeżeli ich licencja pozwala na zastosowanie, dostosowanie i rozpowszechnienie w naszej grze. Paczki dopuszczające wyłącznie użycie niekomercyjne również mogą być brane pod uwagę. Dla każdej dołączonej paczki zapisujemy źródło, wersję, licencję i autorów.

Pierwsza dołączona paczka to [OpenMW Example Suite](https://gitlab.com/OpenMW/example-suite), commit `a41b44d9403ff3f8a1505c1b4bc152c4dd623b64`. Modele i tekstury są udostępnione na CC0 1.0. Pełną listę współtwórców zachowujemy w `licenses/Example-Suite-AUTHORS.md` w paczce Windows, obok oryginalnego pliku licencji. Licencje zależności opisuje również [THIRD_PARTY.md](../THIRD_PARTY.md).

W arenie wykorzystujemy siedem modeli z modułów `the_hub` i `example_static_props`:

| Model | Zastosowanie |
| --- | --- |
| `HubTemple_Pillar01.dae` | Kamienne filary |
| `HubTemple_DoorFrame01.dae` | Kamienne portale przy ścianach areny |
| `Hub_Chest01.dae` | Skrzynie przy obrzeżach |
| `Hub_WeaponStand01.dae` | Stojaki na broń |
| `basic_sword2h.dae` | Miecz bohatera i ekspozycja broni |
| `basic_axe1h.dae` | Topór na stojaku |
| `the_barrel.dae` | Beczki |

Dołączone są również tekstura kamiennej drogi `ground/road_01.dds`, używana na podłożu, oraz trzy tekstury beczki. Skrzynie, beczki i stojaki są obecnie dekoracjami. Bohater i stwór nadal korzystają z modeli i animacji Game Template oraz Animated Creature.

Plik [assets/manifest.json](../assets/manifest.json) wymienia wybrane pliki, ich oryginalne ścieżki, docelowe ścieżki i SHA-256. `tools/setup.py` pobiera wymagane pliki Git LFS i sprawdza ich sumy. Generator sprawdza również sumy każdego wybranego modelu i tekstury przed skopiowaniem do `build/data`; brakujące pliki, wskaźniki LFS i zmienione pliki przerywają budowanie. Jeśli Git dla Windows zamienił końce wierszy modeli XML na CRLF, generator odtwarza LF i akceptuje wynik wyłącznie po zgodności z oryginalnym SHA-256. Do paczki Windows trafiają zweryfikowane bajty upstream i kopia manifestu w `data/echo/asset-manifest.json`.

Do zmiany doboru modeli służą manifest i generator sceny. Zmiana paczki lub wersji wymaga uaktualnienia informacji o źródle i licencji, sum kontrolnych oraz listy pobieranych zasobów w `dependencies.lock.json`.
