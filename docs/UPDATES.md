# Aktualizacje Windows

Pierwszy raz rozpakuj `LowcaEcha-Launcher-Windows-x64.zip` i uruchom `Graj.exe`. Jeśli masz dotychczasową płaską paczkę gry, rozpakuj launcher w tym samym folderze i zastąp `Graj.exe`; katalog `profile` pozostaje na miejscu. Launcher potrafi wykorzystać istniejący silnik i zasoby po sprawdzeniu ich sum. Kolejne aktualizacje pobiera i instaluje sam. Pełny ZIP gry jest alternatywą do instalacji bez pobierania przez launcher.

Repozytorium i jego wydania muszą być publiczne. Launcher korzysta z GitHub Releases bez konta, tokenów i przechowywania danych logowania. Kanał `windows-latest` zawiera `update.json`, mały launcher oraz pełną paczkę gry. Przy braku sieci można uruchomić już zainstalowaną wersję. Niepowodzenie aktualizacji nie przełącza gry na niekompletną wersję.

Wymagany jest systemowy .NET Framework 4.8, dostarczany z Windows 10 od wersji 1903 i Windows 11. Gracz nie instaluje Pythona, Gita ani narzędzi deweloperskich.

**Zapisy i sterowanie launcherem**

- `profile/user/saves`: zapisy wspólne dla wersji.
- `profile/settings.cfg`: zachowywane ustawienia gracza.
- `Graj.exe --offline`: start zainstalowanej gry bez sprawdzania aktualizacji.
- `Graj.exe --rollback`: zamiana bieżącej i poprzedniej wersji oraz start bez sieci. Zgodność zapisów między wersjami gry pozostaje osobnym zagadnieniem.
- `Graj.exe --check`: przygotowanie profilu bez sieci i okna gry, używane przez CI.
- `Graj.exe --test`: 12 testów silnika w osobnym `test-profile`, bez sieci.

**Budowanie i publikowanie**

`python tools/package_windows.py` kompiluje mały bootstrap C, program uruchamiający OpenMW oraz aktualizator C#/.NET. Na Windows korzysta z MSVC i systemowego `csc.exe`; na Linuksie potrzebne są MinGW-w64, Mono `mcs` i biblioteki Mono wymienione w workflow. Niestandardowe kompilatory można wskazać przez `--compiler` i `--csharp-compiler`.

W `dist/` powstają:

- pełny `LowcaEcha-Windows-x64.zip` i jego `.sha256`;
- mały `LowcaEcha-Launcher-Windows-x64.zip` i jego `.sha256`;
- `runtime-<sha256>.zip`: OpenMW, Game Template i stworzenie;
- `game-<sha256>.zip`: kod gry, dodatkowe modele i tekstury, aktualizator, program startowy, konfiguracja domyślna, testy i licencje;
- `update.json`: opis wersji, sumy paczek i każdego pliku.

Po pushu do `main` workflow sprawdza narzędzia, transakcje aktualizacji, odtworzenie rzeczywistych paczek i profil Unicode na Windows, a także grę na Linuksie. Dopiero po sukcesie obu zadań publikuje paczki w wydaniu `windows-<identyfikator wersji>`, a następnie aktualizuje kanał `windows-latest`. Paczki opublikowanych wersji nie są nadpisywane. Starszy przebieg CI nie zastępuje kanału, jeśli `main` wskazuje już nowszy commit. Publikacja korzysta wyłącznie z krótkotrwałego `github.token` w CI z prawem `contents: write`; żadne poświadczenie nie trafia do gry.

**Instalacja transakcyjna**

`Graj.exe` jest stałym punktem wejścia i uruchamia aktualizator z wersji wskazanej przez `current.txt`. Pierwszy start może użyć kopii w `bootstrap/`. Kod aktualizatora jest częścią aktualizowanej paczki gry, więc jego przyszłe zmiany również są dostarczane automatycznie.

Aktualizator porównuje pliki, kopiuje niezmienione paczki lokalnie i pobiera pozostałe przez HTTPS. Sprawdza rozmiary, SHA-256 archiwów i rozpakowanych plików. ZIP może zawierać tylko zadeklarowane pliki wersji; odrzucane są wyjścia poza katalog, pliki profilu, dowiązania, niepoprawne nazwy Windows oraz powtórzone ścieżki. Wersja jest przygotowywana w `.update/stage-*`. Po sprawdzeniu kompletu trafia do nowego katalogu `versions/`, a pojedyncza atomowa zamiana `current.txt` wybiera ją do uruchomienia. Poprzedni wskaźnik trafia do `previous.txt`.

Aktualizacja nie nadpisuje działającego EXE. Blokada folderu zapobiega równoległej grze i aktualizacji przez drugi launcher. Przy następnym starcie usuwane są osierocone katalogi robocze i wersje starsze niż bieżąca oraz poprzednia. Katalog `profile/` nie jest częścią paczek ani sprzątania. Potrzebne jest miejsce na bieżącą i nową wersję.

Testy transakcji: `python tools/test_updater.py`. Test odtworzenia prawdziwej paczki: `python tools/test_updater.py --feed-dir dist`. Oba polecenia na Linuksie korzystają z Mono; można wskazać `--mono` i `--csharp-compiler`.
